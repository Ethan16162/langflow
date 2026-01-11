from lfx.custom.custom_component.component import Component
from lfx.schema.message import Message


class HelloComponent(Component):
    display_name = "Hello 2"
    name = "gys hello"
    description = "Returns hello message"

    def build(self, name: str = "World"):
        return Message(text=f"Hello, {name}!")
