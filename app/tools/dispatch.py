import inspect, typing

def _coerce(value,annotation):
    args=typing.get_args(annotation)
    if args and type(None) in args:
        if value is None:return None
        annotation=next(a for a in args if a is not type(None))
    if annotation is int:
        if isinstance(value,bool): raise ValueError("expected integer")
        if isinstance(value,float) and value.is_integer(): return int(value)
        if isinstance(value,str) and value.strip().lstrip("-").isdigit(): return int(value)
        if isinstance(value,int): return value
        raise ValueError(f"expected integer, got {value!r}")
    if annotation is str and not isinstance(value,str): raise ValueError(f"expected string, got {value!r}")
    return value

def dispatch(functions,name,args):
    fn=functions.get(name)
    if fn is None:return {"error":"unknown_tool","hint":f"Available tools: {', '.join(sorted(functions))}"}
    sig=inspect.signature(fn); hints=typing.get_type_hints(fn)
    try:
        bound=sig.bind(**(args or {}))
        kwargs={k:_coerce(v,hints.get(k)) for k,v in bound.arguments.items()}
    except (TypeError,ValueError) as e:
        return {"error":"invalid_arguments","hint":f"{name}: {e}"}
    return fn(**kwargs)
