from __future__ import annotations
from flask import render_template, request, redirect, url_for, flash
from flask_jwt_extended import jwt_required, get_jwt_identity
from zoneinfo import ZoneInfo, available_timezones
from extensions import db
from auth.models import User
from .. import account_bp
from ..models import AccountProfile

def wants_fragment() -> bool:
    return request.args.get("fragment") == "1" or request.headers.get("X-Fragment") == "1"

@account_bp.route("/", methods=["GET"])
@jwt_required()
def home():
    return redirect(url_for("account.profile"))

def _ensure_profile(user: User) -> AccountProfile:
    prof = user.account_profile
    if prof:
        return prof
    prof = AccountProfile(user_id=user.id)  # timezone='UTC' by default
    db.session.add(prof)
    db.session.commit()
    return prof

def _tz_groups() -> list[tuple[str, list[str]]]:
    try:
        names = sorted(available_timezones())
    except Exception:
        names = [
            "UTC","Asia/Kolkata","Asia/Dubai","Asia/Tokyo","Europe/London",
            "Europe/Berlin","America/New_York","America/Chicago","America/Los_Angeles",
            "Australia/Sydney"
        ]
    banned = ("Etc/", "posix/", "right/", "SystemV/")
    names = [n for n in names if "/" in n and not n.startswith(banned)]
    groups: dict[str, list[str]] = {}
    for n in names:
        region = n.split("/", 1)[0]
        groups.setdefault(region, []).append(n)

    order = ["Asia","Europe","America","Africa","Australia","Pacific","Indian","Atlantic","Antarctica","Arctic","Etc"]
    out: list[tuple[str, list[str]]] = []
    for key in order:
        if key in groups:
            out.append((key, groups.pop(key)))
    for key in sorted(groups.keys()):
        out.append((key, groups[key]))
    return out

@account_bp.route("/profile", methods=["GET", "POST"])
@jwt_required()
def profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("account.home"))

    prof = _ensure_profile(user)
    tz_groups = _tz_groups()

    if request.method == "POST":
        name    = (request.form.get("name") or "").strip()
        tz_raw  = (request.form.get("timezone") or "").strip()
        bio_raw = (request.form.get("bio") or "").strip()

        if name:
            user.name = name

        if tz_raw:
            try:
                _ = ZoneInfo(tz_raw)
                prof.timezone = tz_raw
            except Exception:
                flash("Invalid timezone selected.", "error")

        if bio_raw:
            if len(bio_raw) > 280:
                bio_raw = bio_raw[:280]
                flash("Bio was truncated to 280 characters.", "warning")
            prof.bio = bio_raw
        else:
            prof.bio = None

        db.session.add_all([user, prof])
        db.session.commit()
        flash("Profile updated.", "success")

        if wants_fragment():
            return render_template("account/partials/profile.html", user=user, prof=prof, tz_groups=tz_groups)
        return redirect(url_for("account.profile"))

    if wants_fragment():
        return render_template("account/partials/profile.html", user=user, prof=prof, tz_groups=tz_groups)
    return render_template("account/shell.html", user=user, prof=prof,
                           partial="account/partials/profile.html", tz_groups=tz_groups)
