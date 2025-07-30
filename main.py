# main.py - Cleaned and Corrected Version
from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Employee, Attendance, LeaveRequest
from datetime import date, datetime, timedelta
import models, auth
from schemas import EmployeeLogin
import json

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("/authentication/login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("/authentication/register.html", {"request": request})

@app.post("/register")
def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    repassword: str = Form(...),
    db: Session = Depends(get_db)
):
    if password != repassword:
        return templates.TemplateResponse("/authentication/register.html", {"request": request, "error": "Passwords do not match"})
    
    role_bool = True  # Admin role
    existing = db.query(Employee).filter(Employee.email == email).first()
    if existing:
        return templates.TemplateResponse("/authentication/register.html", {"request": request, "error": "Email already exists"})

    new_employee = Employee(name=name, email=email, role=role_bool)
    new_employee.set_password(password)
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)
    return RedirectResponse("/", status_code=303)

@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        employee = auth.login_user(db, EmployeeLogin(email=email, password=password))
    except:
        return templates.TemplateResponse("/authentication/login.html", {"request": request, "error": "Invalid credentials"})

    if employee.role:
        return RedirectResponse(f"/dashboard?employee_id={employee.id}", status_code=303)
    else:
        return RedirectResponse(f"/employee/dashboard?employee_id={employee.id}", status_code=303)

@app.get("/punch-in", response_class=HTMLResponse)
def punch_in_page(request: Request):
    return templates.TemplateResponse("/authentication/punchin.html", {"request": request})

@app.get("/punch-out", response_class=HTMLResponse)
def punch_out_page(request: Request):
    return templates.TemplateResponse("/authentication/punchout.html", {"request": request})

@app.post("/punch-in")
def punch_in(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    try:
        employee = db.query(Employee).filter(Employee.email == email).first()
        if not employee:
            return RedirectResponse("/punch-in?error=Employee not found", status_code=303)

        today = date.today()
        attendance = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.date == today).first()

        if attendance and attendance.in_time:
            return RedirectResponse("/punch-in?error=Already punched in today", status_code=303)

        if not attendance:
            attendance = Attendance(employee_id=employee.id, date=today, in_time=datetime.now())
            db.add(attendance)
        else:
            attendance.in_time = datetime.now()

        db.commit()
        return RedirectResponse("/punch-in?success=true", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/punch-in?error=System error: {str(e)}", status_code=303)

@app.post("/punch-out")
def punch_out(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    try:
        employee = db.query(Employee).filter(Employee.email == email).first()
        if not employee:
            return RedirectResponse("/punch-out?error=Employee not found", status_code=303)

        today = date.today()
        attendance = db.query(Attendance).filter(Attendance.employee_id == employee.id, Attendance.date == today).first()

        if not attendance:
            return RedirectResponse("/punch-out?error=You haven't punched in today", status_code=303)
        
        if attendance.out_time:
            return RedirectResponse("/punch-out?error=Already punched out today", status_code=303)

        attendance.out_time = datetime.now()
        db.commit()
        return RedirectResponse("/punch-out?success=true", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/punch-out?error=System error: {str(e)}", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)

    employee_id = int(employee_id_str)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.role:
        return RedirectResponse("/", status_code=303)

    # Fetch all employees
    employees = db.query(Employee).filter(Employee.role == False).all()
    total_employees = len(employees)

    # Attendance stats
    today = date.today()
    present_today = db.query(Attendance).filter(
        Attendance.date == today,
        Attendance.in_time != None
    ).count()

    # Pending leaves
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()

    # Dynamic attendance events
    attendance_records = db.query(Attendance).all()
    attendance_events = []
    for record in attendance_records:
        status = "Absent"
        color = "#dc3545"
        if record.in_time and record.out_time:
            status = "Present"
            color = "#198754"
        elif record.in_time or record.out_time:
            status = "Half Day"
            color = "#ffc107"

        employee_name = record.employee.name if record.employee else "Employee"
        attendance_events.append({
            "title": f"{employee_name}: {status}",
            "date": record.date.isoformat(),
            "color": color
        })

    return templates.TemplateResponse("/admin/dashboard.html", {
        "request": request,
        "employee": employee,
        "employees": employees,
        "total_employees": total_employees,
        "present_today": present_today,
        "pending_leaves": pending_leaves,
        "attendance_events": json.dumps(attendance_events)
    })

@app.get("/employee/dashboard", response_class=HTMLResponse)
def employee_dashboard(request: Request, db: Session = Depends(get_db)):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)

    employee_id = int(employee_id_str)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()

    # Only allow non-admins (employees)
    if not employee or employee.role:
        return RedirectResponse("/", status_code=303)

    # Get today’s attendance if exists
    today = date.today()
    attendance_today = db.query(Attendance).filter(
        Attendance.employee_id == employee.id,
        Attendance.date == today
    ).first()

    # Get leave history
    leave_history = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee.id
    ).order_by(LeaveRequest.start_date.desc()).limit(5).all()

    return templates.TemplateResponse("/employee/employee_dashboard.html", {
        "request": request,
        "employee": employee,
        "attendance_today": attendance_today,
        "leave_history": leave_history
    })

@app.get("/attendance", response_class=HTMLResponse)
def attendance_page(request: Request, db: Session = Depends(get_db)):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)
    employee_id = int(employee_id_str)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.role:
        return RedirectResponse("/", status_code=303)

    attendances = db.query(Attendance).filter(Attendance.employee_id == employee.id).all()
    return templates.TemplateResponse("/admin/attendance.html", {
        "request": request,
        "employee": employee,
        "attendances": attendances
    })

@app.post("/attendance/add")
def add_attendance(
    request: Request,
    employee_id: int = Form(...),
    date: date = Form(...),
    in_time: datetime = Form(...),
    out_time: datetime = Form(...),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return RedirectResponse("/attendance?error=Employee not found", status_code=303)

    attendance = Attendance(
        employee_id=employee.id,
        date=date,
        in_time=in_time,
        out_time=out_time
    )
    db.add(attendance)
    db.commit()
    return RedirectResponse("/attendance?success=true", status_code=303)

@app.get("/leave-requests", response_class=HTMLResponse)
def leave_requests(request: Request, db: Session = Depends(get_db)):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)
    employee_id = int(employee_id_str)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.role:
        return RedirectResponse("/", status_code=303)

    leave_requests = db.query(LeaveRequest).filter(LeaveRequest.employee_id == employee.id).all()
    return templates.TemplateResponse("/admin/leave_requests.html", {
        "request": request,
        "employee": employee,
        "leave_requests": leave_requests
    })

@app.post("/leave-request")
def leave_request(
    request: Request,
    employee_id: int = Form(...),
    start_date: date = Form(...),
    end_date: date = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return RedirectResponse("/leave-requests?error=Employee not found", status_code=303)

    new_request = LeaveRequest(
        employee_id=employee.id,
        start_date=start_date,
        end_date=end_date,
        reason=reason
    )
    db.add(new_request)
    db.commit()
    return RedirectResponse("/leave-requests?success=true", status_code=303)

@app.get("/employee/add", response_class=HTMLResponse)
def add_employee_page(request: Request, db: Session = Depends(get_db)):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)
    employee_id = int(employee_id_str)
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.role:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("/admin/add_employee.html", {"request": request, "employee": employee})

@app.post("/employee/add")
def add_employee(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    repassword: str = Form(...),
    db: Session = Depends(get_db)
):
    employee_id_str = request.query_params.get("employee_id")
    if not employee_id_str or not employee_id_str.isdigit():
        return RedirectResponse("/", status_code=303)
    employee_id = int(employee_id_str)
    admin = db.query(Employee).filter(Employee.id == employee_id).first()
    if not admin or not admin.role:
        return RedirectResponse("/", status_code=303)

    if password != repassword:
        return templates.TemplateResponse("/admin/add_employee.html",
            {"request": request, "employee": admin, "error": "Passwords do not match"})
    role_bool = False  # Always employee

    existing = db.query(Employee).filter(Employee.email == email).first()
    if existing:
        return templates.TemplateResponse("/admin/add_employee.html",
            {"request": request, "employee": admin, "error": "Email already exists"})

    new_employee = Employee(
        name=name,
        email=email,
        role=role_bool
    )
    new_employee.set_password(password)
    db.add(new_employee)
    db.commit()
    db.refresh(new_employee)

    # Redirect back to admin dashboard
    return RedirectResponse(f"/dashboard?employee_id={admin.id}", status_code=303)


