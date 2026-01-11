import json
import uuid
from copy import deepcopy

from chromadb.config import Settings
from langchain_chroma import Chroma
from typing_extensions import override

from lfx.base.vectorstores.model import (
    LCVectorStoreComponent,
    check_cached_vector_store,
)
from lfx.base.vectorstores.utils import chroma_collection_to_data
from lfx.inputs.inputs import (
    BoolInput,
    DropdownInput,
    HandleInput,
    IntInput,
    StrInput,
)
from lfx.io import Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class ChromaVectorStoreComponent(LCVectorStoreComponent):
    """Chroma Vector Store with search capabilities."""

    display_name: str = "Chroma DB (gys)"
    description: str = "Chroma Vector Store with search capabilities"
    name = "Chroma"
    icon = "Chroma"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Keep the last search results in memory so that the `selected_results`
        # output can work purely from the last search without needing to hit
        # Chroma again.
        # NOTE: we intentionally keep the original `Data` objects here so that
        # downstream components receive the same structure as the base
        # `LCVectorStoreComponent` while still enriching `data` with stable IDs.
        self._last_search_results: list[Data] = []

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            value="langflow",
        ),
        StrInput(
            name="persist_directory",
            display_name="Persist Directory",
        ),
        *LCVectorStoreComponent.inputs,
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        StrInput(
            name="chroma_server_cors_allow_origins",
            display_name="Server CORS Allow Origins",
            advanced=True,
        ),
        StrInput(
            name="chroma_server_host",
            display_name="Server Host",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_http_port",
            display_name="Server HTTP Port",
            advanced=True,
        ),
        IntInput(
            name="chroma_server_grpc_port",
            display_name="Server gRPC Port",
            advanced=True,
        ),
        BoolInput(
            name="chroma_server_ssl_enabled",
            display_name="Server SSL Enabled",
            advanced=True,
        ),
        BoolInput(
            name="allow_duplicates",
            display_name="Allow Duplicates",
            advanced=True,
            info="If false, will not add documents that are already in the Vector Store.",
        ),
        DropdownInput(
            name="search_type",
            display_name="Search Type",
            options=["Similarity", "MMR"],
            value="Similarity",
            advanced=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=10,
        ),
        IntInput(
            name="limit",
            display_name="Limit",
            advanced=True,
            info="Limit the number of records to compare when Allow Duplicates is False.",
        ),
        StrInput(
            name="selected_result_ids",
            display_name="Selected Result IDs",
            info="JSON array of IDs selected from the previous search.",
        ),
    ]

    outputs = [
        Output(
            display_name="Search Results",
            name="search_results",
            method="search_documents",
        ),
        Output(
            display_name="Selected Results",
            name="selected_results",
            method="get_selected_results",
        ),
        Output(display_name="DataFrame", name="dataframe", method="as_dataframe"),
    ]

    @override
    @check_cached_vector_store
    def build_vector_store(self) -> Chroma:
        """Builds the Chroma object."""
        try:
            from chromadb import Client
            from langchain_chroma import Chroma
        except ImportError as e:
            msg = "Could not import Chroma integration package. Please install it with `pip install langchain-chroma`."
            raise ImportError(msg) from e
        # Chroma settings
        chroma_settings = None
        client = None
        if self.chroma_server_host:
            chroma_settings = Settings(
                chroma_server_cors_allow_origins=self.chroma_server_cors_allow_origins or [],
                chroma_server_host=self.chroma_server_host,
                chroma_server_http_port=self.chroma_server_http_port or None,
                chroma_server_grpc_port=self.chroma_server_grpc_port or None,
                chroma_server_ssl_enabled=self.chroma_server_ssl_enabled,
            )
            client = Client(settings=chroma_settings)

        # Check persist_directory and expand it if it is a relative path
        persist_directory = self.resolve_path(self.persist_directory) if self.persist_directory is not None else None

        chroma = Chroma(
            persist_directory=persist_directory,
            client=client,
            embedding_function=self.embedding,
            collection_name=self.collection_name,
        )

        self._add_documents_to_vector_store(chroma)
        limit = int(self.limit) if self.limit is not None and str(self.limit).strip() else None
        self.status = chroma_collection_to_data(chroma.get(limit=limit))
        return chroma

    def _add_documents_to_vector_store(self, vector_store: "Chroma") -> None:
        """Adds documents to the Vector Store."""
        ingest_data: list | Data | DataFrame = self.ingest_data
        if not ingest_data:
            self.status = ""
            return

        # Convert DataFrame to Data if needed using parent's method
        ingest_data = self._prepare_ingest_data()

        stored_documents_without_id = []
        if self.allow_duplicates:
            stored_data = []
        else:
            limit = int(self.limit) if self.limit is not None and str(self.limit).strip() else None
            stored_data = chroma_collection_to_data(vector_store.get(limit=limit))
            for value in deepcopy(stored_data):
                del value.id
                stored_documents_without_id.append(value)

        documents = []
        for _input in ingest_data or []:
            if isinstance(_input, Data):
                if _input not in stored_documents_without_id:
                    documents.append(_input.to_lc_document())
            else:
                msg = "Vector Store Inputs must be Data objects."
                raise TypeError(msg)

        if documents and self.embedding is not None:
            self.log(f"Adding {len(documents)} documents to the Vector Store.")
            # Filter complex metadata to prevent ChromaDB errors
            try:
                from langchain_community.vectorstores.utils import filter_complex_metadata

                filtered_documents = filter_complex_metadata(documents)
                vector_store.add_documents(filtered_documents)
            except ImportError:
                self.log("Warning: Could not import filter_complex_metadata. Adding documents without filtering.")
                vector_store.add_documents(documents)
        else:
            self.log("No documents to add to the Vector Store.")

    def search_documents(self) -> list[Data]:
        """Search for documents and return a list of `Data` objects with stable IDs.

        The base `LCVectorStoreComponent.search_documents` already returns a list
        of `Data` objects, which are later serialized for the frontend by the
        logging layer. Here we extend that behaviour by:
        - injecting a stable `id` and positional `_index` into each `Data.data`
        - cleaning UTF-8 / nested structures for robustness
        - caching the enriched `Data` objects for the `selected_results` output
        """
        if self._cached_vector_store is not None:
            vector_store = self._cached_vector_store
        else:
            vector_store = self.build_vector_store()
            self._cached_vector_store = vector_store

        search_query: str = self.search_query
        if not search_query:
            self.status = ""
            self._last_search_results = []
            return []

        raw_results = self.search_with_vector_store(
            search_query,
            self.search_type,
            vector_store,
            k=self.number_of_results,
        )

        enriched_results: list[Data] = []
        for index, result in enumerate(raw_results):
            # Ensure each row has a stable ID and index for frontend selection
            rid = result.data.get("id") or str(uuid.uuid4())
            result.data["id"] = rid
            result.data["_index"] = index

            # Clean the payload in-place to avoid serialization issues later
            clean_data_object(result)

            enriched_results.append(result)

        print("~~~~~~~~~~~~~~~~~~~~~~~~~执行search documents~~~~~~~~~~~~~~~~~~")
        # Keep enriched `Data` objects for later reuse
        if not self._last_search_results:
            self._last_search_results = enriched_results
            print("~~~~~~init _last_search_results~~~~~~~")

        # Expose the enriched results via status so that artifacts and logs can
        # serialize them into plain dict rows for the frontend table.
        self.status = enriched_results
        return enriched_results

    def get_selected_results(self) -> list[Data]:
        """Return the subset of documents selected by the user.

        The selection is driven by the `selected_result_ids` input, which the
        frontend fills based on user interaction with the search results table.
        """
        search_results = self._last_search_results or self.search_documents()

        if not search_results:
            self.status = "No search results available. Please run a search first."
            return []

        selected_ids: list[str] = []
        if self.selected_result_ids:
            try:
                if isinstance(self.selected_result_ids, str):
                    selected_ids = json.loads(self.selected_result_ids)
                elif isinstance(self.selected_result_ids, list):
                    selected_ids = self.selected_result_ids
                else:
                    self.log(f"Warning: selected_result_ids has unexpected type: {type(self.selected_result_ids)}")
                    return []
            except (json.JSONDecodeError, TypeError) as exc:
                self.log(f"Error parsing selected_result_ids: {exc}")
                return []

        if not selected_ids:
            self.status = "No results selected. Please select results from the search results."
            return []

        selected_results: list[Data] = []
        selected_ids_str = [str(_id) for _id in selected_ids]

        for result in search_results:
            # Support both `Data` objects and plain dicts, just in case
            data_dict = result.data if hasattr(result, "data") else result
            result_id = data_dict.get("_index")
            # print("------result_id: ", result_id)
            if result_id in selected_ids or str(result_id) in selected_ids_str:
                if hasattr(result, "data"):
                    selected_results.append(clean_data_object(result))
                else:
                    # Fallback: wrap dicts into `Data` so downstream components
                    # receive a consistent type.
                    selected_results.append(Data(data=clean_data_dict(data_dict)))
        # print("======================selected_results:", selected_results)

        self.log(f"Returning {len(selected_results)} selected results out of {len(search_results)} total results.")
        self.status = selected_results
        return selected_results

    def as_dataframe(self) -> DataFrame:
        return DataFrame(self.search_documents())

    def get_retriever_kwargs(self):
        """Get the retriever kwargs. Implementations can override this method to provide custom retriever kwargs."""
        return {}


def clean_utf8_string(value: str) -> str:
    if not isinstance(value, str):
        return value
    try:
        return value.encode("utf-8").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            return value.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        except Exception:
            return ""


def clean_data_dict(obj):
    if isinstance(obj, str):
        return clean_utf8_string(obj)
    if isinstance(obj, dict):
        return {k: clean_data_dict(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean_data_dict(item) for item in obj]
    return obj


def clean_data_object(data_obj: Data) -> Data:
    if hasattr(data_obj, "data"):
        try:
            data_obj.data = clean_data_dict(data_obj.data)
        except Exception:
            pass
    if hasattr(data_obj, "metadata"):
        try:
            data_obj.metadata = clean_data_dict(data_obj.metadata)
        except Exception:
            pass
    return data_obj
