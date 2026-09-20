import sqlite3
from main import DB,init,hp,now
init()
c=sqlite3.connect(DB)
for u,n in [("eva","Eva"),("john","John"),("maya","Maya")]:
    h,s=hp("password123")
    try:c.execute("INSERT INTO users(username,display_name,password_hash,salt,created_at) VALUES(?,?,?,?,?)",(u,n,h,s,now()))
    except sqlite3.IntegrityError:pass
c.commit();c.close()
print("Demo users: eva / john / maya ; password: password123")
