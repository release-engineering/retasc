def update_environment(env):
    env.filters["dunder"] = lambda value: f"__{value}__"
