from app.config import open_stores
def main():
    s,d=open_stores()
    for r in s.conn.execute("SELECT id,status,attempts,error_code FROM run ORDER BY created_at DESC LIMIT 10"):
        print(r["id"][:8],r["status"],"attempts",r["attempts"],r["error_code"] or "")
    print("orders",d.count("canteen_order"),"notifications",d.count("notification"),
          "idempotency",d.count("idempotency"))
if __name__=="__main__":main()
