#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Author  : linghypshen@gmail.com
@File    : 1.RunnableComponentLifecycleListener.py
"""
import time

from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import RunnableLambda
from langchain_core.tracers.schemas import Run


def on_start(run_obj: Run, config: RunnableConfig) -> None:
    print("on_start")
    print("run_obj:", run_obj)
    print("config:", config)
    print("============")


def on_end(run_obj: Run, config: RunnableConfig) -> None:
    print("on_end")
    print("run_obj:", run_obj)
    print("config:", config)
    print("============")


def on_error(run_obj: Run, config: RunnableConfig) -> None:
    print("on_error")
    print("run_obj:", run_obj)
    print("config:", config)
    print("============")


# 1. Create RunnableLambda and chain
runnable = RunnableLambda(lambda x: time.sleep(x)).with_listeners(
    on_start=on_start,
    on_end=on_end,
    on_error=on_error,
)
chain = runnable

# 2. Invoke and execute the chain
chain.invoke(2, config={"configurable": {"name": "Ling"}})

# https://github.com/geekan/MetaGPT/tree/main/metagpt/memory
