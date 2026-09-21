import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base,Student,MenuItem
DATABASE_URL=os.getenv("CANTEEN_DATABASE_URL","sqlite:///./canteen.db")
engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False})
SessionLocal=sessionmaker(autocommit=False,autoflush=False,bind=engine)
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def init_db():
    Base.metadata.create_all(bind=engine)
    db=SessionLocal()
    try:
        if db.query(Student).count()==0:
            db.add_all([Student(name="Arun Kumar",email="arun@college.edu",wallet_balance=250),Student(name="Meena Raj",email="meena@college.edu",wallet_balance=180),Student(name="Viviyan Prince",email="viviyan@college.edu",wallet_balance=500)])
        if db.query(MenuItem).count()==0:
            db.add_all([MenuItem(name="Samosa",category="Snacks",price=15,portions_available=20),MenuItem(name="Masala Dosa",category="Breakfast",price=45,portions_available=10),MenuItem(name="Veg Fried Rice",category="Lunch",price=70,portions_available=12),MenuItem(name="Paneer Roll",category="Snacks",price=55,portions_available=8),MenuItem(name="Lemon Juice",category="Drinks",price=25,portions_available=15),MenuItem(name="Coffee",category="Drinks",price=20,portions_available=25)])
        db.commit()
    finally: db.close()
