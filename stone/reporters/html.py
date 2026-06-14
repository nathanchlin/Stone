"""HTML reporter using Jinja templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from stone.selector.engine import SelectionResult

_TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class HtmlReporter:
    """Render HTML reports from templates."""

    def __init__(self, template_dir: Path | None = None):
        tmpl_dir = template_dir or _TEMPLATE_DIR
        self.env = Environment(
            loader=FileSystemLoader(str(tmpl_dir)),
            autoescape=select_autoescape(["html"]),
        )

    def render(self, result: SelectionResult, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        template = self.env.get_template("report.html.j2")
        html = template.render(result=result)
        out = output_dir / f"{result.target_date.isoformat()}_{result.strategy_name}.html"
        out.write_text(html, encoding="utf-8")
        return out
