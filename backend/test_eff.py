from app.engines.scalping.config import ScalpingConfig, default_config

cfg = ScalpingConfig(use_optimized=True, active_profiles=[], profiles={})
wfo = default_config()

eff = cfg.model_copy(update={
    "active_profiles": wfo.active_profiles,
    "profiles": wfo.profiles,
    "tiered_tp": wfo.tiered_tp,
})
print("wfo.active_profiles:", wfo.active_profiles)
print("eff.active_profiles:", eff.active_profiles)
print("eff.profiles keys:", eff.profiles.keys())
