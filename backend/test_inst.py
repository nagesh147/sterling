from app.services.exchanges import instrument_registry as registry
inst = registry.get_instrument("ETH")
print("Has options:", getattr(inst, "has_options", False))
