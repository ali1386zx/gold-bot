import tkinter as tk
from tkinter import ttk, messagebox
import requests
import threading
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ⚠️ کلید API خود را اینجا وارد کنید
API_KEY = "Z0xpaVRSZqJxL1GO0Nf1X9TAWGJcD0QRMXGRi3uZgY" 

# ⚠️⚠️⚠️ آدرس دقیق API را از قسمت "مستندات" داخل پنل کاربری خود کپی کنید ⚠️⚠️⚠️
# مثال: "https://api.nerkh.io/v1/price" 
URL = "https://api.nerkh.io/v1/prices/json/gold"


def fetch_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-API-Key": API_KEY,
        "Accept": "application/json"
    }

    # اگر در مستندات سایت گفته بود کلید را در URL بفرستید، خط زیر را فعال کنید و headers را پاک کنید:
    # URL_WITH_KEY = f"{URL}?key={API_KEY}"
    
    try:
        resp = requests.get(URL, headers=headers, timeout=10, verify=False)
        
        # اگر بازم HTML آمد، یعنی آدرس را اشتباه زدید
        if resp.text.strip().startswith("<!DOCTYPE") or resp.text.strip().startswith("<html"):
            return "HTML_ERROR"
            
        resp.raise_for_status()
        data = resp.json()
        
        # استخراج لیست از داخل دیکشنری (با توجه به ساختار مختلف سایت‌ها)
        if isinstance(data, dict):
            if "data" in data:
                data = data["data"]
            elif "results" in data:
                data = data["results"]
            elif "items" in data:
                data = data["items"]
                
        return data
        
    except requests.exceptions.JSONDecodeError:
        return "JSON_ERROR"
    except Exception as e:
        return f"EXCEPTION: {str(e)}"

def update_display():
    def task():
        btn.config(state="disabled")
        for row in tree.get_children():
            tree.delete(row)

        data = fetch_prices()
        
        if data == "HTML_ERROR":
            messagebox.showerror("خطای آدرس", "بازهم صفحه وب (HTML) دریافت شد!\nآدرس URL را از بخش «مستندات API» داخل پنل کاربری بردارید، نه آدرس خود پنل را.")
            btn.config(state="normal")
            return
        elif data == "JSON_ERROR":
            messagebox.showerror("خطا", "پاسخ سرور استاندارد نبود. آدرس یا کلید API را بررسی کنید.")
            btn.config(state="normal")
            return
        elif isinstance(data, str) and data.startswith("EXCEPTION:"):
            messagebox.showerror("خطای اتصال", data.replace("EXCEPTION: ", ""))
            btn.config(state="normal")
            return

        if isinstance(data, list):
            for item in data:
                name = item.get("name") or item.get("title") or item.get("symbol", "---")
                
                price_raw = item.get("price") or item.get("latest_price") or 0
                try:
                    price = int(float(price_raw))
                except:
                    price = 0

                change_raw = item.get("change_value") or item.get("change") or 0
                try:
                    change_val = int(float(change_raw))
                except:
                    change_val = 0

                change_pct = item.get("change_percent") or item.get("change_percentage") or 0
                unit = item.get("unit") or "تومان"

                tree.insert("", "end", values=(
                    name,
                    f"{price:,} {unit}",
                    f"{change_val:,}",
                    f"{change_pct}%"
                ))
        else:
            messagebox.showwarning("توجه", f"ساختار پاسخ لیست نیست:\n{str(data)[:200]}")

        btn.config(state="normal")

    threading.Thread(target=task).start()

root = tk.Tk()
root.title("قیمت لحظه‌ای طلا و ارز | Nerkh.io")
root.geometry("650x450")
root.option_add("*Font", "Tahoma 10")

frame = tk.Frame(root)
frame.pack(pady=10, padx=10, fill="both", expand=True)

cols = ("نام", "قیمت", "تغییر (مبلغ)", "تغییر (درصد)")
tree = ttk.Treeview(frame, columns=cols, show="headings", height=16)

tree.column("نام", width=150, anchor="center")
tree.column("قیمت", width=150, anchor="center")
tree.column("تغییر (مبلغ)", width=130, anchor="center")
tree.column("تغییر (درصد)", width=120, anchor="center")

for col in cols:
    tree.heading(col, text=col)

scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
scrollbar.pack(side="right", fill="y")
tree.configure(yscrollcommand=scrollbar.set)
tree.pack(side="left", fill="both", expand=True)

btn = tk.Button(root, text="بروزرسانی قیمت‌ها", command=update_display, font=("Tahoma", 11, "bold"), bg="#4CAF50", fg="white", padx=10, pady=5)
btn.pack(pady=10)

root.after(500, update_display)
root.mainloop()