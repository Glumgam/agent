class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name, func):
        if not name:
            raise ValueError("tool name is required")
        if not callable(func):
            raise ValueError("tool function must be callable")
        self._tools[name] = func

    def get(self, name):
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        return self._tools[name]

    def list_tools(self):
        return sorted(self._tools.keys())


registry = ToolRegistry()
