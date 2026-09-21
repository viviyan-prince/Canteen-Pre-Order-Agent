import argparse
from app.config import open_stores
def main():
    p=argparse.ArgumentParser(); p.add_argument("student_id"); p.add_argument("text",nargs="+"); a=p.parse_args()
    s,d=open_stores(); tid=s.create_thread(a.student_id); rid=s.enqueue(tid," ".join(a.text),"mock")
    print("Queued:",rid)
    print("Run: python -m scripts.worker --mock --once")
if __name__=="__main__":main()
