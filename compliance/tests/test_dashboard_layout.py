from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HTML = (ROOT / "dashboard" / "static" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "dashboard" / "static" / "style.css").read_text(encoding="utf-8")


def test_dashboard_exposes_light_and_dark_theme_controls():
    assert 'data-theme="dark"' in HTML
    assert 'id="theme-button"' in HTML
    assert ':root[data-theme="light"]' in CSS
    assert 'localStorage.getItem("aiops-theme")' in HTML


def test_desktop_dashboard_uses_single_viewport_workspace():
    assert 'class="dashboard-shell"' in HTML
    assert 'class="dashboard-grid"' in HTML
    assert "html, body { width: 100%; height: 100%; overflow: hidden; }" in CSS
    assert "grid-template-rows: 66px minmax(0, 1fr) 28px;" in CSS
    assert "grid-template-columns: minmax(300px, .92fr) minmax(390px, 1.08fr) minmax(520px, 1.48fr);" in CSS


def test_long_content_scrolls_inside_panels_not_the_page():
    assert HTML.count('class="tab-panel panel-scroll') >= 2
    assert 'class="report-panel panel-scroll"' in HTML
    assert 'class="tab-panel detail-panel panel-scroll active"' in HTML
    assert ".panel-scroll" in CSS
    assert "overflow: auto;" in CSS
