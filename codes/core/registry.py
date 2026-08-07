# -*- coding: utf-8 -*-
"""模块注册表：按名称注册并运行决策处理模块。

配合 config/deployment.json 的 enabled 字段决定哪些模块启用。
纯标准库 json。
"""

import json

# 名称 -> 可调用函数 fn(data)
REGISTRY = {}


def register(name, fn):
    """注册一个模块：name 字符串，fn 接收 data 参数并返回结果。"""
    REGISTRY[name] = fn
    return fn  # 可作装饰器 @register("x")


def enabled_modules(config) -> list:
    """读取部署配置(config 为 deployment.json 路径)，返回启用的模块名列表。"""
    with open(config, "r", encoding="utf-8") as f:
        conf = json.load(f)
    return list(conf.get("enabled", []))


def run_module(name, data):
    """运行已注册模块 name，传入 data，返回其结果。未注册则报错。"""
    if name not in REGISTRY:
        raise KeyError(f"模块未注册: {name}")
    return REGISTRY[name](data)
