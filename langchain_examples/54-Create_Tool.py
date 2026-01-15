#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.Create_Tool_With_At_Tool_Decorator.py
# """
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool


class MultiplyInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


@tool("multiply_tool", return_direct=True, args_schema=MultiplyInput)
def multiply(a: int, b: int) -> int:
    """Multiply the two provided numbers"""
    return a * b


# Print out the tool's information
print("Name: ", multiply.name)
print("Description: ", multiply.description)
print("Arguments: ", multiply.args)
print("Return Directly: ", multiply.return_direct)

# Invoke the tool
print(multiply.invoke({"a": 2, "b": 8}))

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 2.Create_Tool_Using_StructuredTool_Class.py
"""
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import StructuredTool


class MultiplyInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


def multiply(a: int, b: int) -> int:
    """Multiply the two provided numbers"""
    return a * b


async def amultiply(a: int, b: int) -> int:
    """Multiply the two provided numbers (async version)"""
    return a * b


calculator = StructuredTool.from_function(
    func=multiply,
    coroutine=amultiply,
    name="multiply_tool",
    description="Multiply the two provided numbers",
    return_direct=True,
    args_schema=MultiplyInput,
)

# Print the tool's metadata
print("Name: ", calculator.name)
print("Description: ", calculator.description)
print("Arguments: ", calculator.args)
print("Return Directly: ", calculator.return_direct)

# Invoke the tool
print(calculator.invoke({"a": 2, "b": 8}))

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 3.Create_Tool_Using_BaseTool_Subclass.py
"""
from typing import Any, Type

from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool


class MultiplyInput(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


class MultiplyTool(BaseTool):
    """Multiplication tool"""
    name = "multiply_tool"
    description = "Multiply the two provided numbers and return the result"
    args_schema: Type[BaseModel] = MultiplyInput

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """Multiply a and b and return the result"""
        return kwargs.get("a") * kwargs.get("b")


calculator = MultiplyTool()

# Print tool metadata
print("Name: ", calculator.name)
print("Description: ", calculator.description)
print("Arguments: ", calculator.args)
print("Return Directly: ", calculator.return_direct)

# Invoke the tool
print(calculator.invoke({"a": 2, "b": 8}))
