from extensions import db
from support.models import SupportSetting
from flask import current_app

# Keys we allow to override from DB (others remain env-only)
ALLOWED_SETTING_KEYS = {
    "SUPPORT_PENDING_REMINDER_DAYS": int,
    "SUPPORT_AUTO_CLOSE_DAYS": int,
    "SUPPORT_MAX_UPLOAD_MB": int,
    "SUPPORT_ALLOWED_MIME": list,
    "SUPPORT_ALLOWED_EXT": list,
}

def get_effective_settings():
    """
    Merge app.config defaults with DB overrides (ALLOWED_SETTING_KEYS only).
    """
    eff = {k: current_app.config.get(k) for k in ALLOWED_SETTING_KEYS.keys()}
    for row in SupportSetting.query.all():
        if row.key in ALLOWED_SETTING_KEYS:
            eff[row.key] = row.value
    return eff

def upsert_settings(changes: dict[str, object]):
    """
    Upsert DB overrides and also update current_app.config at runtime.
    """
    updated = {}
    for key, caster in ALLOWED_SETTING_KEYS.items():
        if key not in changes:
            continue
        val = changes[key]
        # treat null as delete override
        if val is None:
            # delete override if present
            row = SupportSetting.query.filter_by(key=key).first()
            if row:
                db.session.delete(row)
            # reset runtime config back to original default
            current_app.config[key] = current_app.config.get(key)
            updated[key] = None
            continue

        # cast/validate
        try:
            if caster is int:
                val = int(val)
            elif caster is list:
                if isinstance(val, str):
                    # allow comma-separated
                    val = [x.strip() for x in val.split(",") if x.strip()]
                elif not isinstance(val, list):
                    raise ValueError("must be list or comma-separated string")
        except Exception:
            raise ValueError(f"invalid value for {key}")

        row = SupportSetting.query.filter_by(key=key).first()
        if not row:
            row = SupportSetting(key=key, value=val)
            db.session.add(row)
        else:
            row.value = val
        current_app.config[key] = val
        updated[key] = val
    return updated
