from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session
from ..models import ops as dbmodels


def create_inspection_report(building_id: int, db: Session) -> str:
    b = db.query(dbmodels.Building).filter_by(id=building_id).first()
    path = f"data/inspection_report_{building_id}.pdf"
    c = canvas.Canvas(path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 760, "Inspection Report")
    c.setFont("Helvetica", 11)
    if not b:
        c.drawString(50, 730, f"Building ID {building_id} not found.")
        c.save()
        return path
    y = 730
    lines = [
        f"Building ID: {b.id}",
        f"Construction year: {b.construction_year}",
        f"Floors: {b.num_floors}",
        f"Apartments: {b.num_apartments}",
        f"Latitude, Longitude: {b.latitude}, {b.longitude}",
        f"Total kWh: {b.total_kwh}",
        "Anomaly Summary: (placeholder for AE/IF scores)",
    ]
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.showPage()
    c.save()
    return path

