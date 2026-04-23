"""Tests for reporting.html_template components."""

import unittest
from reporting.html_template import (
    esc,
    html_open,
    html_close,
    stat_card,
    stat_grid,
    section_open,
    section_close,
    card,
    badge,
    fidelity_bar,
    donut_chart,
    bar_chart,
    data_table,
    tab_bar,
    tab_content,
    flow_diagram,
    cmd_box,
    get_report_css,
    get_report_js,
)


class TestEsc(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(esc("<b>hi</b>"), "&lt;b&gt;hi&lt;/b&gt;")

    def test_ampersand(self):
        self.assertEqual(esc("a & b"), "a &amp; b")

    def test_quotes(self):
        self.assertIn("&quot;", esc('"hello"'))

    def test_non_string(self):
        self.assertEqual(esc(42), "42")


class TestHtmlOpen(unittest.TestCase):
    def test_contains_title(self):
        html = html_open("My Report")
        self.assertIn("<title>My Report</title>", html)
        self.assertIn("<!DOCTYPE html>", html)

    def test_contains_subtitle(self):
        html = html_open("T", subtitle="sub text")
        self.assertIn("sub text", html)

    def test_contains_version(self):
        html = html_open("T", version="2.0")
        self.assertIn("v2.0", html)

    def test_contains_css(self):
        html = html_open("T")
        self.assertIn("--pbi-blue", html)
        self.assertIn("<style>", html)

    def test_theme_toggle_button(self):
        html = html_open("T")
        self.assertIn("theme-toggle", html)
        self.assertIn("toggleTheme", html)


class TestHtmlClose(unittest.TestCase):
    def test_contains_footer(self):
        html = html_close()
        self.assertIn("report-footer", html)
        self.assertIn("</html>", html)

    def test_contains_js(self):
        html = html_close()
        self.assertIn("function toggleSection", html)
        self.assertIn("function sortTable", html)

    def test_version_in_footer(self):
        html = html_close(version="1.5")
        self.assertIn("v1.5", html)


class TestStatCard(unittest.TestCase):
    def test_basic(self):
        html = stat_card(42, "Items")
        self.assertIn("42", html)
        self.assertIn("Items", html)
        self.assertIn("stat-card", html)

    def test_accent(self):
        html = stat_card(5, "Err", accent="fail")
        self.assertIn("accent-fail", html)

    def test_custom_color(self):
        html = stat_card(5, "X", color="#ff0000")
        self.assertIn('color:#ff0000', html)


class TestStatGrid(unittest.TestCase):
    def test_wraps_cards(self):
        cards = [stat_card(1, "A"), stat_card(2, "B")]
        html = stat_grid(cards)
        self.assertIn("stat-grid", html)
        self.assertIn("A", html)
        self.assertIn("B", html)


class TestSection(unittest.TestCase):
    def test_open_close(self):
        html = section_open("s1", "Section One", icon="X")
        self.assertIn("s1", html)
        self.assertIn("Section One", html)
        self.assertIn("toggleSection", html)
        close = section_close()
        self.assertIn("</div>", close)

    def test_collapsed(self):
        html = section_open("s2", "Two", collapsed=True)
        self.assertIn("collapsed", html)


class TestCard(unittest.TestCase):
    def test_basic(self):
        html = card(content="<p>stuff</p>", title="Title")
        self.assertIn("Title", html)
        self.assertIn("<p>stuff</p>", html)
        self.assertIn('class="card"', html)

    def test_no_title(self):
        html = card(content="body")
        self.assertNotIn("<h3>", html)


class TestBadge(unittest.TestCase):
    def test_explicit_level(self):
        html = badge("OK", level="green")
        self.assertIn("badge-green", html)
        self.assertIn("OK", html)

    def test_inferred_success(self):
        html = badge("EXACT")
        self.assertIn("badge-green", html)

    def test_inferred_fail(self):
        html = badge("UNSUPPORTED")
        self.assertIn("badge-red", html)

    def test_inferred_warn(self):
        html = badge("APPROXIMATE")
        self.assertIn("badge-yellow", html)

    def test_inferred_gray(self):
        html = badge("SKIPPED")
        self.assertIn("badge-gray", html)

    def test_unknown_defaults_gray(self):
        html = badge("custom")
        self.assertIn("badge-gray", html)


class TestFidelityBar(unittest.TestCase):
    def test_high(self):
        html = fidelity_bar(98.5)
        self.assertIn("98.5%", html)
        self.assertIn("var(--success)", html)

    def test_mid(self):
        html = fidelity_bar(85.0)
        self.assertIn("#c19c00", html)

    def test_low(self):
        html = fidelity_bar(50.0)
        self.assertIn("var(--fail)", html)


class TestDonutChart(unittest.TestCase):
    def test_basic(self):
        html = donut_chart([("A", 10, "#ff0000"), ("B", 20, "#00ff00")])
        self.assertIn("<svg", html)
        self.assertIn("donut-container", html)
        self.assertIn("A", html)
        self.assertIn("B", html)
        self.assertIn("#ff0000", html)

    def test_center_text(self):
        html = donut_chart([("X", 5, "#000")], center_text="5")
        self.assertIn(">5<", html)

    def test_empty(self):
        html = donut_chart([])
        self.assertIn("donut-container", html)


class TestBarChart(unittest.TestCase):
    def test_basic(self):
        html = bar_chart([("Foo", 10, "#0078d4"), ("Bar", 5, "#038387")])
        self.assertIn("bar-chart", html)
        self.assertIn("Foo", html)
        self.assertIn("Bar", html)

    def test_auto_max(self):
        html = bar_chart([("A", 100, "#000")])
        self.assertIn("100.0%", html)


class TestDataTable(unittest.TestCase):
    def test_basic(self):
        html = data_table(["Col1", "Col2"], [["a", "b"], ["c", "d"]], table_id="t1")
        self.assertIn("Col1", html)
        self.assertIn("<td>a</td>", html)

    def test_sortable(self):
        html = data_table(["X"], [["v"]], table_id="t2", sortable=True)
        self.assertIn("sortable", html)
        self.assertIn("sortTable", html)

    def test_searchable(self):
        html = data_table(["X"], [["v"]], table_id="t3", searchable=True)
        self.assertIn("filterTable", html)
        self.assertIn('placeholder="Filter rows..."', html)

    def test_detail_style(self):
        html = data_table(["X"], [["v"]], table_id="t4", detail=True)
        self.assertIn("detail-table", html)


class TestTabBar(unittest.TestCase):
    def test_basic(self):
        html = tab_bar("grp", [("t1", "Tab 1", True), ("t2", "Tab 2", False)])
        self.assertIn("tab-bar", html)
        self.assertIn("Tab 1", html)
        self.assertIn("active", html)
        self.assertIn("switchTab", html)


class TestTabContent(unittest.TestCase):
    def test_active(self):
        html = tab_content("grp", "t1", "<p>hello</p>", active=True)
        self.assertIn("active", html)
        self.assertIn("<p>hello</p>", html)

    def test_inactive(self):
        html = tab_content("grp", "t2", "body")
        self.assertNotIn("active", html.split('class="')[1].split('"')[0])


class TestFlowDiagram(unittest.TestCase):
    def test_basic(self):
        html = flow_diagram([("Step 1", False), ("Step 2", True)])
        self.assertIn("flow-container", html)
        self.assertIn("Step 1", html)
        self.assertIn("Step 2", html)
        self.assertIn("flow-arrow", html)

    def test_accent(self):
        html = flow_diagram([("X", True)])
        self.assertIn("accent", html)


class TestCmdBox(unittest.TestCase):
    def test_basic(self):
        html = cmd_box("python migrate.py --help")
        self.assertIn("cmd-box", html)
        self.assertIn("python migrate.py --help", html)
        self.assertIn("prompt", html)

    def test_escaping(self):
        html = cmd_box("<script>alert(1)</script>")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class TestCSSAndJS(unittest.TestCase):
    def test_css_not_empty(self):
        css = get_report_css()
        self.assertIn("--pbi-blue", css)
        self.assertIn("dark", css)
        self.assertIn("@media print", css)

    def test_js_not_empty(self):
        js = get_report_js()
        self.assertIn("toggleSection", js)
        self.assertIn("filterTable", js)
        self.assertIn("sortTable", js)
        self.assertIn("toggleTheme", js)


if __name__ == "__main__":
    unittest.main()
