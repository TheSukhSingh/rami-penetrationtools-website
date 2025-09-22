# tools/seed_config.py
from extensions import db
from tools.models import Tool, ToolConfigField, ToolConfigFieldType

COMMON = [
  {"name":"input_method","label":"Input Source","type":"select","default":"manual",
   "choices":[{"value":"manual","label":"Manual value"},{"value":"file","label":"Server file"}],
   "order_index":0},
  {"name":"value","label":"Value / Domain","type":"string","placeholder":"example.com","order_index":1},
  {"name":"file_path","label":"Input File Path","type":"path","order_index":2},
]

EXTRAS = {
  "subfinder": [],
  "gau": [{"name":"providers","label":"Providers","type":"string",
           "default":"wayback,otx,commoncrawl","order_index":3}],
  "httpx": [{"name":"threads","label":"Threads","type":"integer","default":50,"order_index":3}],
  # add as needed for your 10 tools
}

def seed(slug: str, fields: list[dict]):
    tool = Tool.query.filter_by(slug=slug).first()
    if not tool: 
        print("missing tool:", slug); return
    ToolConfigField.query.filter_by(tool_id=tool.id).delete()
    for i,f in enumerate(fields):
        db.session.add(ToolConfigField(
            tool_id=tool.id,
            name=f["name"],
            label=f.get("label", f["name"]),
            type=ToolConfigFieldType(f.get("type","string")),
            required=bool(f.get("required", False)),
            help_text=f.get("help_text"),
            placeholder=f.get("placeholder"),
            default=f.get("default"),
            choices=f.get("choices"),
            group=f.get("group"),
            order_index=int(f.get("order_index", i)),
            advanced=bool(f.get("advanced", False)),
            visible=bool(f.get("visible", True)),
        ))
    print("seeded:", slug)

def run():
    for tool in Tool.query.all():
        fields = COMMON + EXTRAS.get(tool.slug, [])
        seed(tool.slug, fields)
    db.session.commit()
    print("done.")

if __name__ == "__main__":
    # run with FLASK_APP=app.py python -c "from tools.seed_config import run; run()"
    run()
