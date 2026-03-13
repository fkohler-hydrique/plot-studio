"""Templates tab renderer."""

import datetime
import json
import uuid

import streamlit as st

from plot_studio.services.columns import normalize_colname
from plot_studio.services.templates import persist_saved_configs_to_disk


def render_templates_tab() -> None:
    """Render template management UI."""
    st.markdown("#### Templates")
    st.caption("Manage templates (rename, delete, export/import, edit JSON).")

    configs = st.session_state["saved_configs"]
    if not configs:
        st.info("No templates saved yet.")
        return

    ordered = sorted(configs, key=lambda cfg: (cfg.get("name") or "").lower())
    id_to_cfg = {cfg.get("id"): cfg for cfg in ordered}
    sel_id = st.selectbox(
        "Select template",
        options=[cfg.get("id") for cfg in ordered],
        format_func=lambda value: id_to_cfg[value].get("name", "Unnamed"),
    )
    sel = id_to_cfg.get(sel_id)

    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="top")
    with c1:
        new_name = st.text_input("Rename", value=sel.get("name", ""))
        if st.button("Apply rename", width="stretch"):
            sel["name"] = new_name.strip() or sel.get("name", "")
            persist_saved_configs_to_disk(configs)
            st.success("Renamed.")
    with c2:
        st.download_button(
            "Export selected (JSON)",
            data=json.dumps(sel, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=(
                f"{normalize_colname(sel.get('name', 'template')).replace(' ', '_') or 'template'}.json"
            ),
            mime="application/json",
            width="stretch",
        )
    with c3:
        if st.button("Delete selected", type="secondary", width="stretch"):
            st.session_state["saved_configs"] = [
                cfg for cfg in configs if cfg.get("id") != sel_id
            ]
            persist_saved_configs_to_disk(st.session_state["saved_configs"])
            if st.session_state.get("active_dashboard_id") == sel_id:
                st.session_state["active_dashboard_id"] = None
            st.success("Deleted.")
            st.rerun()

    st.divider()

    with st.expander("Edit template JSON (advanced)", expanded=False):
        edited = st.text_area(
            "Template JSON",
            value=json.dumps(sel, ensure_ascii=False, indent=2),
            height=380,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Validate JSON", width="stretch"):
                try:
                    json.loads(edited)
                    st.success("Valid JSON.")
                except Exception as exc:
                    st.error(f"Invalid JSON: {exc}")
        with col_b:
            if st.button("Save JSON to template", width="stretch"):
                try:
                    new_obj = json.loads(edited)
                    if not isinstance(new_obj, dict):
                        st.error("Template JSON must be an object.")
                    else:
                        new_obj.setdefault("id", sel_id)
                        new_configs = []
                        for cfg in configs:
                            if cfg.get("id") == sel_id:
                                new_configs.append(new_obj)
                            else:
                                new_configs.append(cfg)
                        st.session_state["saved_configs"] = new_configs
                        persist_saved_configs_to_disk(new_configs)
                        st.success("Template updated.")
                        st.rerun()
                except Exception as exc:
                    st.error(f"Could not save: {exc}")

    st.divider()
    st.markdown("##### Import template JSON")
    upl = st.file_uploader(
        "Import a template (.json)", type=["json"], key="import_json"
    )
    if upl is not None:
        try:
            imported = json.loads(upl.getvalue().decode("utf-8"))
            if not isinstance(imported, dict):
                st.error("Imported file must be a JSON object.")
            else:
                imported.setdefault("id", str(uuid.uuid4()))
                imported.setdefault(
                    "created_at",
                    datetime.datetime.utcnow().isoformat() + "Z",
                )
                imported.setdefault("plots", [])
                st.session_state["saved_configs"].append(imported)
                persist_saved_configs_to_disk(st.session_state["saved_configs"])
                st.success("Imported template.")
        except Exception as exc:
            st.error(f"Import failed: {exc}")
