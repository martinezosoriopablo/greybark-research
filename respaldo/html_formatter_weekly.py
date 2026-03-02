from pathlib import Path
from html_formatter import build_html_from_md, INPUT_DIR

def main():
    print("=== Convirtiendo reportes SEMANALES .md a HTML (Optimizado para Email) ===")
    md_files = sorted(p for p in INPUT_DIR.glob("*.md") if p.name.startswith("weekly_report_"))
    if not md_files:
        print("[WARN] No se encontraron archivos weekly_report_*.md en la carpeta actual.")
        return
    for md in md_files:
        try:
            build_html_from_md(md)
        except Exception as e:
            print(f"[ERROR] Error con {md.name}: {e}")
    print("[OK] Conversión semanal completada")

if __name__ == "__main__":
    main()
