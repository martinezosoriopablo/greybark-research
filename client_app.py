# app.py
import streamlit as st
import pandas as pd

from client_manager import (
    load_database,
    save_database,
    add_client,
    remove_client,
    update_client_reports,
    AVAILABLE_REPORTS,
    CLIENT_TYPES,
    get_recipients_for_report,
)

# Opcional: habilita envío desde la UI
# from send_email_report_improved import send_report_email

st.set_page_config(page_title="Grey Bark - Clientes & Reportes", layout="wide")
st.title("Grey Bark Advisors — Gestión de Clientes y Reportes")

db = load_database()
clients = db.get("clients", [])

# ---------------------------
# Helpers
# ---------------------------
def clients_df():
    rows = []
    for c in clients:
        rows.append({
            "id": c["id"],
            "name": c["name"],
            "email": c["email"],
            "type": c["type"],
            "active": bool(c["active"]),
            "reports": ", ".join(c.get("reports", [])),
            "notes": c.get("notes", "")
        })
    return pd.DataFrame(rows)

def find_client_by_email(email: str):
    for c in clients:
        if c["email"].lower() == email.lower():
            return c
    return None

# ---------------------------
# Layout
# ---------------------------
tab1, tab2, tab3 = st.tabs(["Clientes", "Asignación de reportes", "Destinatarios por reporte"])

with tab1:
    st.subheader("Listado")
    df = clients_df()
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("Agregar nuevo cliente")

    with st.form("add_client_form", clear_on_submit=True):
        name = st.text_input("Nombre completo")
        email = st.text_input("Email")
        client_type = st.selectbox("Tipo", CLIENT_TYPES)
        report_keys = list(AVAILABLE_REPORTS.keys())
        report_labels = [f"{AVAILABLE_REPORTS[k]} ({k})" for k in report_keys]
        selected = st.multiselect("Reportes", options=report_keys, format_func=lambda k: f"{AVAILABLE_REPORTS[k]} ({k})")
        notes = st.text_area("Notas (opcional)", height=80)
        submitted = st.form_submit_button("Agregar")

        if submitted:
            if not name or not email:
                st.error("Nombre y email son obligatorios.")
            elif client_type not in CLIENT_TYPES:
                st.error("Tipo inválido.")
            else:
                ok = add_client(name=name, email=email, client_type=client_type, reports=selected, notes=notes)
                if ok:
                    st.success("Cliente agregado. Recarga automática recomendada (F5) si no aparece de inmediato.")
                else:
                    st.error("No se pudo agregar (¿email duplicado?).")

    st.divider()
    st.subheader("Activar / Desactivar cliente")
    email_toggle = st.text_input("Email del cliente", key="toggle_email")
    colA, colB = st.columns(2)

    with colA:
        if st.button("Desactivar"):
            if email_toggle:
                ok = remove_client(email_toggle)
                if ok:
                    st.success("Cliente desactivado.")
                else:
                    st.error("No encontrado.")
            else:
                st.warning("Ingresa un email.")

    with colB:
        if st.button("Activar"):
            if not email_toggle:
                st.warning("Ingresa un email.")
            else:
                c = find_client_by_email(email_toggle)
                if not c:
                    st.error("No encontrado.")
                else:
                    c["active"] = True
                    save_database(db)
                    st.success("Cliente activado.")

with tab2:
    st.subheader("Actualizar reportes de un cliente")
    email_edit = st.text_input("Email del cliente", key="edit_email")
    if email_edit:
        c = find_client_by_email(email_edit)
        if not c:
            st.error("Cliente no encontrado.")
        else:
            st.write(f"**Cliente:** {c['name']}  \n**Tipo:** {c['type']}  \n**Activo:** {bool(c['active'])}")
            current = c.get("reports", [])
            selected = st.multiselect(
                "Reportes asignados",
                options=list(AVAILABLE_REPORTS.keys()),
                default=current,
                format_func=lambda k: f"{AVAILABLE_REPORTS[k]} ({k})"
            )
            if st.button("Guardar cambios"):
                ok = update_client_reports(email_edit, selected)
                if ok:
                    st.success("Reportes actualizados.")
                else:
                    st.error("No se pudo actualizar.")

    st.divider()
    st.subheader("Opcional: Enviar un reporte desde la UI")
    st.caption("Recomendado solo para uso interno. Las credenciales SMTP siguen en tu .env.")
    report_to_send = st.selectbox("Tipo de reporte", list(AVAILABLE_REPORTS.keys()))
    # if st.button("Enviar ahora"):
    #     ok = send_report_email(report_to_send)
    #     st.success("Enviado") if ok else st.error("Falló el envío (revisar logs).")

with tab3:
    st.subheader("Ver destinatarios por tipo de reporte")
    r = st.selectbox("Selecciona reporte", list(AVAILABLE_REPORTS.keys()), format_func=lambda k: f"{AVAILABLE_REPORTS[k]} ({k})")
    rec = get_recipients_for_report(r)
    if rec:
        st.write(f"**Destinatarios ({len(rec)}):**")
        st.table(pd.DataFrame(rec))
    else:
        st.info("No hay destinatarios para este reporte.")
