from datetime import datetime
from enum import Enum
import re
from sqlalchemy import CheckConstraint, event
from sqlalchemy.orm.attributes import get_history

from extensions import db
import math
from markupsafe import escape as html_escape

# Optional deps; we handle absence gracefully
try:
    import markdown as _mdlib
except Exception:
    _mdlib = None

try:
    import bleach as _bleach
except Exception:
    _bleach = None

USER_FK = "users.id"

_SLUGIFY_RE = re.compile(r"[^a-z0-9]+")

def slugify(text: str) -> str:
    """
    Minimal, dependency-free slugify.
    Keeps a-z0-9 and hyphens. Lowercases & trims.
    """
    text = (text or "").strip().lower()
    text = _SLUGIFY_RE.sub("-", text)
    text = text.strip("-")
    return text or "post"

post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)

post_assets = db.Table(
    "post_assets",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id", ondelete="CASCADE"), primary_key=True),
    db.Column("asset_id", db.Integer, db.ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True),
)
# -------- Markdown rendering + sanitization + reading time --------

# very small word regex for counting; good enough for reading-time
_WORD_RE = re.compile(r"\w+")

# bleach allowlists (only used if bleach is installed)
_ALLOWED_TAGS = [
    "p","br","hr",
    "h1","h2","h3","h4","h5","h6",
    "strong","em","blockquote",
    "ul","ol","li",
    "code","pre","span","div","kbd",
    "a","img",
    "table","thead","tbody","tr","th","td"
]
_ALLOWED_ATTRS = {
    "a": ["href","title","rel","target"],
    "img": ["src","alt","title","width","height"],
    "code": ["class"],
    "pre":  ["class"],
    "span": ["class"],
    "div":  ["class"],
    "th": ["colspan"], 
    "td": ["colspan"]
}
_ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

def render_markdown_to_html(md_text: str) -> str:
    """
    Render Markdown to HTML (with fenced code and codehilite) and sanitize.
    """
    text = md_text or ""

    if _mdlib is not None:
        # Explicitly enable fenced code + codehilite
        html = _mdlib.markdown(
            text,
            extensions=[
                "extra",            # includes tables, etc.
                "sane_lists",
                "toc",
                "fenced_code",      # triple-backticks
                "codehilite"        # wraps in <div class="codehilite"><pre>…
            ],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "noclasses": False,   # keep CSS classes like language-bash
                }
            }
        )
    else:
        # minimal fallback
        html = "<p>" + html_escape(text).replace("\r\n","\n") \
                                        .replace("\n\n","</p><p>") \
                                        .replace("\n","<br>") + "</p>"

    if _bleach is not None:
        html = _bleach.clean(
            html,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            protocols=_ALLOWED_PROTOCOLS,
            strip=True,
        )
        # Do not linkify inside code/pre/highlight wrappers
        html = _bleach.linkify(html, skip_tags=["pre","code","div","span"])
    return html

def compute_reading_time(md_text: str, wpm: int = 200) -> int:
    """
    Approximate reading time in minutes (min 1).
    """
    nwords = len(_WORD_RE.findall(md_text or ""))
    return max(1, math.ceil(nwords / float(wpm)))

class Category(db.Model):
    __tablename__ = "category"

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255))         # optional, shows on category page
    sort_order  = db.Column(db.Integer)             # optional, to order categories in UI

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category {self.slug}>"

class Tag(db.Model):
    __tablename__ = "tag"

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Tag {self.slug}>"

class Asset(db.Model):
    """
    Storing the images - both cover images and inside blog images
    Path will look like: /uploads/blog/YYYY/MM/<unique>.<ext>
    """
    __tablename__ = "asset"

    id        = db.Column(db.Integer, primary_key=True)
    path      = db.Column(db.String(512), unique=True, nullable=False)
    mime      = db.Column(db.String(100), nullable=False)
    byte_size = db.Column(db.Integer)
    width     = db.Column(db.Integer)
    height    = db.Column(db.Integer)
    sha256    = db.Column(db.String(64), index=True)  # useful for dedupe
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Asset {self.path}>"
    
class PostStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    
    
class Post(db.Model):
    """
    Posts are stored in MD format
    """
    __tablename__ = "post"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','in_review','scheduled','published','archived')",
            name="ck_post_status_allowed"
        ),
    )

    id    = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    slug  = db.Column(db.String(220), unique=True, index=True, nullable=False)

    summary    = db.Column(db.Text)         # meta/OG description source
    body_md    = db.Column(db.Text, nullable=False)
    body_html  = db.Column(db.Text)         # rendered+sanitized HTML cache
    reading_time = db.Column(db.Integer)     # minutes

    status = db.Column(db.String(20), nullable=False, index=True, default=PostStatus.DRAFT.value)    
    published_at = db.Column(db.DateTime, index=True)

    cover_path   = db.Column(db.String(512)) # public URL path to cover
    cover_alt  = db.Column(db.String(180)) 

    og_title       = db.Column(db.String(180))
    og_description = db.Column(db.String(200))

    category_id = db.Column(db.Integer, db.ForeignKey("category.id", ondelete="SET NULL"))
    category    = db.relationship("Category")

    author_id = db.Column(db.Integer, db.ForeignKey(USER_FK, ondelete="SET NULL"))  # change USER_FK if needed

    tags   = db.relationship("Tag",   secondary=post_tags,   lazy="joined")
    assets = db.relationship("Asset", secondary=post_assets, lazy="selectin")

    featured  = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def ensure_slug(self):
        if not self.slug:
            self.slug = slugify(self.title)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Post {self.slug} status={self.status}>"

class SlugRedirect(db.Model):
    """
    Keeps old → new slug mappings so external links never break.
    """
    __tablename__ = "slug_redirect"

    id       = db.Column(db.Integer, primary_key=True)
    entity   = db.Column(db.String(20), default="post", nullable=False)
    old_slug = db.Column(db.String(220), unique=True, index=True, nullable=False)
    new_slug = db.Column(db.String(220), index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SlugRedirect {self.old_slug}→{self.new_slug}>"

# ------------------------
# events: auto-slug + slug history
# ------------------------
@event.listens_for(Post, "before_insert")
def _post_before_insert(mapper, connection, target: Post):  # pragma: no cover
    target.ensure_slug()
    target.body_html   = render_markdown_to_html(target.body_md or "")
    target.reading_time = compute_reading_time(target.body_md or "")


@event.listens_for(Post, "before_update")
def _post_before_update(mapper, connection, target: Post):  # pragma: no cover
    # --- existing slug redirect logic ---
    slug_hist = get_history(target, "slug")
    if slug_hist.has_changes():
        old = slug_hist.deleted[0] if slug_hist.deleted else None
        new = slug_hist.added[0]   if slug_hist.added   else None
        if old and new and old != new:
            connection.execute(
                SlugRedirect.__table__.insert().values(
                    entity="post",
                    old_slug=old,
                    new_slug=new,
                    created_at=datetime.utcnow(),
                )
            )

    # --- NEW: re-render body & reading-time when markdown changes ---
    md_hist = get_history(target, "body_md")
    if md_hist.has_changes():
        # These helpers come from Step 2 you added in models.py
        target.body_html    = render_markdown_to_html(target.body_md or "")
        target.reading_time = compute_reading_time(target.body_md or "")
