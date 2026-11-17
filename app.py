import os
from dotenv import load_dotenv
load_dotenv()
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import URL
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-secret-key")

app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "salary_budget"),
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(150),unique=True,nullable=False,index=True)
    password_hash=db.Column(db.String(255),nullable=False)
    def set_password(self,p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)

class Budget(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True)
    month=db.Column(db.String(7),nullable=False); salary=db.Column(db.Numeric(12,2),nullable=False)
    rent=db.Column(db.Numeric(12,2),default=0); emi=db.Column(db.Numeric(12,2),default=0)
    bills=db.Column(db.Numeric(12,2),default=0); other_fixed=db.Column(db.Numeric(12,2),default=0)
    savings=db.Column(db.Numeric(12,2),default=0)
    __table_args__=(db.UniqueConstraint("user_id","month",name="uq_user_budget_month"),)

class Expense(db.Model):
    id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey("user.id"),nullable=False,index=True)
    budget_id=db.Column(db.Integer,db.ForeignKey("budget.id"),nullable=False,index=True)
    amount=db.Column(db.Numeric(12,2),nullable=False); category=db.Column(db.String(60),nullable=False)
    description=db.Column(db.String(255),default=""); spent_on=db.Column(db.Date,nullable=False,default=date.today)
    budget=db.relationship("Budget")

@login_manager.user_loader
def load_user(uid): return db.session.get(User,int(uid))

def month_now(): return date.today().strftime("%Y-%m")
def days_in_month(m):
    y,mo=map(int,m.split("-")); return (date(y+(mo==12),1 if mo==12 else mo+1,1)-date(y,mo,1)).days
def amount(v):
    try:
        x=Decimal(str(v or 0))
        if x<0: raise InvalidOperation
        return x.quantize(Decimal("0.01"))
    except (InvalidOperation,TypeError): raise ValueError("Enter valid non-negative amounts.")
def find_budget(uid,m): return Budget.query.filter_by(user_id=uid,month=m).first()
def summary(b):
    fixed=sum((amount(getattr(b,k)) for k in ("rent","emi","bills","other_fixed","savings")),Decimal("0"))
    available=amount(b.salary)-fixed
    es=Expense.query.filter_by(user_id=b.user_id,budget_id=b.id).all()
    spent=sum((amount(e.amount) for e in es),Decimal("0"))
    today=sum((amount(e.amount) for e in es if e.spent_on==date.today()),Decimal("0"))
    remaining=available-spent
    daysleft=max(1,days_in_month(b.month)-date.today().day+1) if b.month==month_now() else days_in_month(b.month)
    cats={}
    for e in es: cats[e.category]=cats.get(e.category,Decimal("0"))+amount(e.amount)
    return dict(salary=amount(b.salary),fixed=fixed,available=available,spent=spent,remaining=remaining,
                daily=available/Decimal(days_in_month(b.month)),today=today,today_limit=max(Decimal("0"),remaining/Decimal(daysleft)),
                categories=sorted(cats.items(),key=lambda x:x[1],reverse=True))
@app.context_processor
def inject_date(): return {"today_iso":date.today().isoformat(),"now_month":month_now()}

@app.route("/")
def index(): return redirect(url_for("dashboard")) if current_user.is_authenticated else render_template("index.html")
@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if not name or not email or len(pw)<8: flash("Provide name, email, and password (at least 8 characters).","error")
        elif User.query.filter_by(email=email).first(): flash("Email already registered.","error")
        else:
            u=User(name=name,email=email); u.set_password(pw); db.session.add(u); db.session.commit(); login_user(u); return redirect(url_for("dashboard"))
    return render_template("register.html")
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if u and u.check_password(request.form.get("password","")): login_user(u); return redirect(url_for("dashboard"))
        flash("Invalid email or password.","error")
    return render_template("login.html")
@app.route("/logout")
@login_required
def logout(): logout_user(); return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    m=request.args.get("month",month_now())
    if len(m)!=7 or m[4]!="-": m=month_now()
    b=find_budget(current_user.id,m)
    es=Expense.query.filter_by(user_id=current_user.id,budget_id=b.id).order_by(Expense.spent_on.desc(),Expense.id.desc()).limit(12).all() if b else []
    return render_template("dashboard.html",budget=b,summary=summary(b) if b else None,expenses=es,month=m,
        categories=["Food","Transport","Shopping","Bills","Health","Entertainment","Education","Other"])
@app.route("/budget",methods=["GET","POST"])
@login_required
def budget():
    m=request.args.get("month",month_now()); b=find_budget(current_user.id,m)
    if request.method=="POST":
        m=request.form.get("month",month_now())
        try:
            vals={k:amount(request.form.get(k)) for k in ("salary","rent","emi","bills","other_fixed","savings")}
            if vals["salary"]<=0: raise ValueError("Salary must be greater than zero.")
            if sum((vals[k] for k in ("rent","emi","bills","other_fixed","savings")),Decimal("0"))>vals["salary"]:
                raise ValueError("Fixed expenses and savings cannot exceed salary.")
            b=find_budget(current_user.id,m)
            if not b: b=Budget(user_id=current_user.id,month=m); db.session.add(b)
            for k,v in vals.items(): setattr(b,k,v)
            db.session.commit(); flash("Budget saved.","success"); return redirect(url_for("dashboard",month=m))
        except ValueError as e: flash(str(e),"error")
        b=find_budget(current_user.id,m)
    return render_template("budget.html",budget=b,month=m)
@app.route("/expenses/add",methods=["POST"])
@login_required
def add_expense():
    m=request.form.get("month",month_now()); b=find_budget(current_user.id,m)
    if not b: flash("Create a budget first.","error"); return redirect(url_for("budget",month=m))
    try:
        amt=amount(request.form.get("amount")); d=date.fromisoformat(request.form.get("spent_on"))
        if amt<=0: raise ValueError
        if d.strftime("%Y-%m")!=m: raise ValueError
        db.session.add(Expense(user_id=current_user.id,budget_id=b.id,amount=amt,category=request.form.get("category","Other"),description=request.form.get("description","").strip()[:255],spent_on=d))
        db.session.commit(); flash("Expense added.","success")
    except (ValueError,TypeError): flash("Enter a valid amount and date in the selected month.","error")
    return redirect(url_for("dashboard",month=m))
@app.route("/expenses/<int:eid>/delete",methods=["POST"])
@login_required
def delete_expense(eid):
    e=Expense.query.filter_by(id=eid,user_id=current_user.id).first_or_404(); m=e.budget.month
    db.session.delete(e); db.session.commit(); flash("Expense deleted.","success"); return redirect(url_for("dashboard",month=m))
@app.route("/expenses")
@login_required
def expenses():
    m=request.args.get("month",month_now()); b=find_budget(current_user.id,m)
    entries=Expense.query.filter_by(user_id=current_user.id,budget_id=b.id).order_by(Expense.spent_on.desc()).all() if b else []
    return render_template("expenses.html",entries=entries,month=m)
@app.cli.command("init-db")
def init_db(): db.create_all(); print("Database tables created.")
if __name__=="__main__":
    with app.app_context(): db.create_all()
    app.run(debug=os.getenv("FLASK_DEBUG","1")=="1")
