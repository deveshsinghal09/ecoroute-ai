"""Experimental artifacts may be evaluated, but never become navigation forecasts."""


def operational_dataset(manifest):
    return (
        manifest.get("training_scope") == "delhi_station_operational"
        and manifest.get("synthetic") is False
        and manifest.get("feature_availability_verified") is True
    )


def operational_model(manifest):
    return manifest.get("verified") is True and operational_dataset(
        manifest.get("dataset_manifest", {})
    )
