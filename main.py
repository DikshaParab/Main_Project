import asyncio
from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, date
from fastapi import Query
import auth
import models

from database import SessionLocal, engine, get_db


models.Base.metadata.create_all(bind=engine)

app = FastAPI()

def get_next_admin_id(db: Session) -> int:
    max_admin_id = db.query(models.User).filter(models.User.role == True).order_by(models.User.admin_id.desc()).first()
    if max_admin_id and max_admin_id.admin_id:
        return max_admin_id.admin_id + 1
    return 1

def get_next_employee_id(db: Session) -> int:
    max_employee_id = db.query(models.User).filter(models.User.role == False).order_by(models.User.employee_id.desc()).first()
    if max_employee_id and max_employee_id.employee_id:
        return max_employee_id.employee_id + 1
    return 1


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Authentication Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: int = None, db: Session = Depends(get_db)):
    if user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = auth.get_user_by_id(db, user_id)
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if user.role:
        return RedirectResponse(url=f"/admin/dashboard/{user.id}")
    return RedirectResponse(url=f"/employee/dashboard/{user.id}")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("authentication/login.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    action: str = Form(None),
    db: Session = Depends(get_db)
):
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if not db_user:
        return templates.TemplateResponse("authentication/login.html", {
            "request": request,
            "error": "Email not registered. Please register first."
        })

    await asyncio.sleep(0.5)
    
    user = auth.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse("authentication/login.html", {
            "request": request,
            "error": "Invalid password. Please try again."
        })

    
    if user.role:  # Admin
        return RedirectResponse(url=f"/admin/dashboard/{user.id}", status_code=303)
    else:  # Employee
        if action == "punchin":
            today = date.today()
            existing = db.query(models.Attendance).filter(
                models.Attendance.user_id == user.id,
                models.Attendance.date == today
            ).first()
            punch_time = datetime.now()
            if existing and existing.check_in:
                pass
            elif existing:
                existing.check_in = punch_time
            else:
                new_attendance = models.Attendance(
                    user_id=user.id,
                    date=today,
                    check_in=punch_time,
                )
                db.add(new_attendance)
            db.commit()
            return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchin=success", status_code=303)
        elif action == "punchout":
            today = date.today()
            attendance = db.query(models.Attendance).filter(
                models.Attendance.user_id == user.id,
                models.Attendance.date == today
            ).first()
            if attendance and attendance.check_in and not attendance.check_out:
                attendance.check_out = datetime.now()
                db.commit()
                return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchout=success", status_code=303)
            else:
                return RedirectResponse(url=f"/employee/dashboard/{user.id}", status_code=303)
        else:
            return RedirectResponse(url=f"/employee/dashboard/{user.id}", status_code=303)
    
@app.get("/logout", response_class=HTMLResponse)
async def logout(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(url="/login", status_code=303)

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("authentication/register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    # Check if any admin user exists
    admin_exists = db.query(models.User).filter(models.User.role == True).first()
    if admin_exists:
        return templates.TemplateResponse("authentication/register.html", 
            {"request": request, "error": "Registration is closed. Please contact admin."})
    
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if db_user:
        return templates.TemplateResponse("authentication/register.html", 
            {"request": request, "error": "Email already registered"})
    
    hashed_password = auth.get_password_hash(password)
    new_user = models.User(
        email=email,
        name=name,
        password_hash=hashed_password,
        role=True,  # First user is admin
        admin_id=get_next_admin_id(db)
    )
    db.add(new_user)
    db.commit()
    
    return RedirectResponse(url="/login", status_code=303)

# Admin Routes
@app.get("/admin/dashboard/{user_id}", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    try:
        user = auth.get_current_user(db, user_id)
       
        employee_count = db.query(models.User).filter(models.User.employee_id.isnot(None)).count()
        present_count = db.query(models.Attendance).filter(
            models.Attendance.date == date.today(),
            models.Attendance.check_in.isnot(None)
        ).count()
        pending_leaves = db.query(models.Leave).filter(models.Leave.status == "pending").count()
        recent_activities = []  
        
        return templates.TemplateResponse("admin/dashboard.html", {
            "request": request,
            "user": user,
            "employee_count": employee_count,
            "present_count": present_count,
            "pending_leaves": pending_leaves,
            "recent_activities": recent_activities
        })
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/admin/add-employee/{user_id}", response_class=HTMLResponse)
async def add_employee_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, user_id)
    if not user.role:
        return RedirectResponse(url="/employee/dashboard", status_code=303)
    return templates.TemplateResponse("admin/add_employee.html", {"request": request, "user": user})

@app.post("/admin/add-employee/{user_id}", response_class=HTMLResponse)
async def add_employee_post(
    request: Request,
    user_id: int,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: int = Form(0),
    db: Session = Depends(get_db)
):
    user = auth.get_current_user(db, user_id)
    if not user.role:
        return RedirectResponse(url="/employee/dashboard", status_code=303)
    
    db_user = db.query(models.User).filter(models.User.email == email).first()
    if db_user:
        return templates.TemplateResponse("admin/add_employee.html", 
            {"request": request, "error": "Email already registered", "user": user})
    
    hashed_password = auth.get_password_hash(password)
    new_user = models.User(
        email=email,
        name=name,
        password_hash=hashed_password,
        role=bool(role),
        admin_id=get_next_admin_id(db) if role else None,
        employee_id=get_next_employee_id(db) if not role else None
    )
    db.add(new_user)
    db.commit()
    
    # Flash message simulation by passing success message to template
    return templates.TemplateResponse("admin/add_employee.html", 
        {"request": request, "user": user, "success": "New employee added successfully."})

@app.get("/admin/add-employee/employee/{employee_id}", response_class=HTMLResponse)
async def add_employee_by_employee_id(
    request: Request,
    employee_id: int,
    db: Session = Depends(get_db)
):
    employee = db.query(models.User).filter(models.User.employee_id == employee_id).first()
    if not employee:
        return RedirectResponse(url="/admin/employees", status_code=303)
    return templates.TemplateResponse("admin/add_employee.html", {"request": request, "user": employee})

@app.get("/admin/log-history/{user_id}", response_class=HTMLResponse)
async def admin_log_history(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, user_id)
    if not user.role:
        return RedirectResponse(url="/employee/dashboard", status_code=303)
    
    employees = db.query(models.User).filter(models.User.role == False).all()
    attendance_records = db.query(models.Attendance).order_by(models.Attendance.date.desc()).all()
    
    return templates.TemplateResponse("admin/log_history.html",
        {"request": request, "user": user, "employees": employees, "attendance_records": attendance_records})

@app.get("/admin/profile/{user_id}", response_class=HTMLResponse)
async def admin_profile(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, user_id)
    if not user.role:
        return RedirectResponse(url="/employee/dashboard", status_code=303)
    
    return templates.TemplateResponse("admin/profile.html",
        {"request": request, "user": user})

@app.get("/admin/employees/{user_id}", response_class=HTMLResponse)
async def admin_employees(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, user_id)
    if not user.role:
        return RedirectResponse(url="/employee/dashboard", status_code=303)
    
    employees = db.query(models.User).filter(models.User.role == False).all()
    return templates.TemplateResponse("admin/employees.html", 
        {"request": request, "user": user, "employees": employees})

@app.get("/admin/leave-requests/{user_id}")
async def admin_leave_requests(
    request: Request,
    user_id: int,
    status: str = Query("pending"),
    db: Session = Depends(get_db)
):
    try:
        current_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not current_user or not current_user.role:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Validate status filter
        valid_statuses = ["pending", "approved", "rejected", "all"]
        if status not in valid_statuses:
            status = "pending"
        
        # Build query
        query = db.query(models.Leave)
        if status != "all":
            query = query.filter(models.Leave.status == status)
        
        # Get sorted leaves
        leaves = query.order_by(models.Leave.created_at.desc()).all()
        
        return templates.TemplateResponse(
            "admin/leave_requests.html",
            {
                "request": request,
                "user": current_user,
                "leaves": leaves,
                "status_filter": status
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/leave/decision/{leave_id}")
async def process_leave_decision(
    leave_id: int,
    decision: str = Form(...),
    user_id: int = Form(...),  
    db: Session = Depends(get_db)
):
    try:
        admin_user = db.query(models.User).filter(
            models.User.id == user_id,
            models.User.role == True  # Ensure it's an admin
        ).first()
        
        if not admin_user:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Get the leave request
        leave = db.query(models.Leave).filter(models.Leave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=404, detail="Leave request not found")

        if decision not in ["approve", "reject"]:
            raise HTTPException(status_code=400, detail="Invalid decision")

        # Update leave status
        leave.status = "approved" if decision == "approve" else "rejected"
        leave.processed_by = admin_user.id
        leave.processed_at = datetime.now()
        
        db.commit()
        
        return RedirectResponse(
            url=f"/admin/leave-requests/{admin_user.id}?status=pending",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# Employee Routes

@app.get("/employee/dashboard/{user_id}", response_class=HTMLResponse)
async def employee_dashboard(request: Request, user_id: int, punchin: str = Query(None), punchout: str = Query(None), db: Session = Depends(get_db)):
    try:
        user = auth.get_current_user(db, user_id)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)
    if user.role:
        return RedirectResponse(url=f"/admin/dashboard/{user.id}", status_code=303)
    
    print(user.role, 'userasdasdasdasdasd')
    today = date.today()
    attendance = db.query(models.Attendance).filter(
        models.Attendance.user_id == user.id,
        models.Attendance.date == today
    ).first()
    punchin_success = None
    punchout_success = None
    if punchin == "success":
        punchin_success = "Punch-in successful!"
    if punchout == "success":
        punchout_success = "Punch-out successful!"

    return templates.TemplateResponse("employee/employee_dashboard.html", 
        {"request": request, "user": user, "attendance": attendance, "punchin_success": punchin_success, "punchout_success": punchout_success})

@app.post("/employee/punch-in/{user_id}", response_class=HTMLResponse)
async def employee_punch_in(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    user = auth.get_current_user(db, user_id)
    today = date.today()
    print(today, 'today')
    existing = db.query(models.Attendance).filter(
        models.Attendance.user_id == user.id,
        models.Attendance.date == today
    ).first()
    
    if existing and existing.check_in:
        return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchin=success", status_code=303)
    
    punch_time = datetime.now()
    
    if existing:
        existing.check_in = punch_time
    else:
        new_attendance = models.Attendance(
            user_id=user.id,
            date=today,
            check_in=punch_time,
        )
        db.add(new_attendance)
    
    db.commit()
    return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchin=success", status_code=303)

@app.post("/employee/punch-out/{user_id}", response_class=HTMLResponse)
async def employee_punch_out(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    user = auth.get_current_user(db, user_id)
    today = date.today()
    
    attendance = db.query(models.Attendance).filter(
        models.Attendance.user_id == user.id,
        models.Attendance.date == today
    ).first()
    
    if not attendance or not attendance.check_in or attendance.check_out:
        return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchout=success", status_code=303)
    
    punch_time = datetime.now()
    attendance.check_out = punch_time
    
    db.commit()
    return RedirectResponse(url=f"/employee/dashboard/{user.id}?punchout=success", status_code=303)

@app.get("/employee/leave/{user_id}", response_class=HTMLResponse)
async def employee_leave(
    request: Request,
    user_id: int,
    success: str = Query(None),
    error: str = Query(None),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        leaves = db.query(models.Leave)\
            .filter(models.Leave.user_id == user_id)\
            .order_by(models.Leave.from_date.desc())\
            .all()
            
        return templates.TemplateResponse(
            "employee/employee_leaves.html",
            {
                "request": request,
                "user": user,
                "leaves": leaves,
                "success": success,
                "error": error
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/employee/leave/{user_id}", response_class=HTMLResponse)
async def apply_leave(
    request: Request,
    user_id: int,
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        today = date.today()
        
        if start_date < today:
            return RedirectResponse(
                url=f"/employee/leave/{user_id}?error=Cannot+apply+for+past+dates",
                status_code=303
            )
            
        if start_date > end_date:
            return RedirectResponse(
                url=f"/employee/leave/{user_id}?error=End+date+must+be+after+start+date",
                status_code=303
            )
        
        overlapping = db.query(models.Leave).filter(
            models.Leave.user_id == user_id,
            models.Leave.status.in_(["pending", "approved"]),
            models.Leave.from_date <= end_date,
            models.Leave.to_date >= start_date
        ).first()
        
        if overlapping:
            return RedirectResponse(
                url=f"/employee/leave/{user_id}?error=You+already+have+a+leave+for+this+period",
                status_code=303
            )
        
        # Create new leave
        new_leave = models.Leave(
            user_id=user.id,
            from_date=start_date,
            to_date=end_date,
            reason=reason,
            status="pending",
            created_at=datetime.now()
        )
        
        db.add(new_leave)
        db.commit()
        
        return RedirectResponse(
            url=f"/employee/leave/{user_id}?success=Leave+applied+successfully",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/employee/attendance/{user_id}", response_class=HTMLResponse)
async def employee_attendance(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db)
):
    try:
        current_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not current_user:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        attendance_records = db.query(models.Attendance)\
            .filter(models.Attendance.user_id == user_id)\
            .order_by(models.Attendance.date.desc())\
            .all()
        
        # Calculate stats
        present_days = len([r for r in attendance_records if r.check_in])
        absent_days = 30 - present_days  
        
        return templates.TemplateResponse(
            "employee/employee_attendance.html",
            {
                "request": request,
                "user": current_user,
                "attendance_records": attendance_records,
                "present_days": present_days,
                "absent_days": absent_days
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/employee/profile/{user_id}", response_class=HTMLResponse)
async def employee_profile(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = auth.get_current_user(db, user_id)
    if user.role:
        return RedirectResponse(url=f"/admin/dashboard/{user.id}", status_code=303)
    
    return templates.TemplateResponse("employee/employee_profile.html", {"request": request, "user": user})
