import os
import csv
import json
import sqlite3
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# --- 1. ВІДКРИТЕ ДЖЕРЕЛО ДАНИХ ---
# URL обраного джерела: https://books.toscrape.com/index.html
BASE_URL = "https://books.toscrape.com/"
INDEX_URL = urljoin(BASE_URL, "index.html")

print("--- КРОК 2: Завантаження та перевірка статичності сторінки ---")
response = requests.get(INDEX_URL)
response.encoding = "utf-8"

# Перевірка статус-коду
if response.status_code == 200:
    print(f"Сторiнку успішно завантажено. Статус: {response.status_code}")
else:
    print(f"Помилка завантаження: {response.status_code}")
    exit()

soup = BeautifulSoup(response.text, "html.parser")

# --- 3. ОТРИМАННЯ СПИСКУ ПІДРОЗДІЛІВ (КАТЕГОРІЙ) ---
# На сайті категорії знаходяться в блоці <div class="side_categories"> -> <ul> -> <ul> -> <li> -> <a>
categories_data = []
side_categories = soup.find("div", class_="side_categories")
category_links = side_categories.find_all("a") if side_categories else []

for link in category_links:
    cat_name = link.get_text(strip=True)
    cat_url = urljoin(BASE_URL, link["href"])
    categories_data.append({"name": cat_name, "url": cat_url})

print(f"Знайдено підрозділів (категорій): {len(categories_data)}")

# Зберігаємо список підрозділів у текстовий файл
with open("categories.txt", "w", encoding="utf-8") as f:
    for cat in categories_data:
        f.write(f"Назва: {cat['name']} | URL: {cat['url']}\n")

# Зберігаємо список підрозділів у форматі XML
root_xml = ET.Element("categories")
for cat in categories_data:
    item_elem = ET.SubElement(root_xml, "category")
    name_elem = ET.SubElement(item_elem, "name")
    name_elem.text = cat["name"]
    url_elem = ET.SubElement(item_elem, "url")
    url_elem.text = cat["url"]

tree = ET.ElementTree(root_xml)
tree.write("categories.xml", encoding="utf-8", xml_declaration=True)
print("Підрозділи збережено у файли: categories.txt, categories.xml")


# --- 4. СКРАПІНГ ОБ'ЄКТІВ (КНИЖОК) З КОЖНОГО ПІДРОЗДІЛУ ---
all_books = []
images_data = []

os.makedirs("images", exist_ok=True)

print("\n--- КРОК 4 та 5: Збір об'єктів (книжок) та зображень ---")
# Обмежимо для прикладу першими 3 категоріями
for cat in categories_data[:3]:
    print(f"Скрапінг категорії: {cat['name']}...")
    cat_resp = requests.get(cat["url"])
    cat_resp.encoding = "utf-8"
    cat_soup = BeautifulSoup(cat_resp.text, "html.parser")

    books = cat_soup.find_all("article", class_="product_pod")
    for book in books:
        # Назва та посилання на книгу
        title_tag = book.h3.find("a")
        book_title = title_tag["title"]
        book_url = urljoin(cat["url"], title_tag["href"])

        # Ціна
        price_tag = book.find("p", class_="price_color")
        book_price = price_tag.get_text(strip=True) if price_tag else ""

        # Зображення
        img_tag = book.find("img")
        if img_tag:
            img_rel_url = img_tag["data-src"] if "data-src" in img_tag.attrs else img_tag["src"]
            img_url = urljoin(BASE_URL, img_rel_url)
            img_name = os.path.basename(img_url)
            img_path = os.path.join("images", img_name)

            # Завантаження зображення (Крок 5)
            try:
                img_data = requests.get(img_url).content
                with open(img_path, "wb") as img_file:
                    img_file.write(img_data)
                images_data.append({"image_name": img_name, "url": img_url, "local_path": img_path})
            except Exception as e:
                print(f"Помилка завантаження картинки {img_url}: {e}")

        all_books.append({
            "category": cat["name"],
            "title": book_title,
            "url": book_url,
            "price": book_price
        })

# Збереження об'єктів до текстового файлу
with open("books.txt", "w", encoding="utf-8") as f:
    for book in all_books:
        f.write(f"[{book['category']}] {book['title']} - {book['price']} ({book['url']})\n")

# Збереження об'єктів у форматі JSON
with open("books.json", "w", encoding="utf-8") as f:
    json.dump(all_books, f, ensure_ascii=False, indent=4)

print(f"Зібрано об'єктів (книжок): {len(all_books)}")


# --- 5. ЗБЕРЕЖЕННЯ СПИСКУ ЗОБРАЖЕНЬ ---
# У текстовий формат
with open("images_list.txt", "w", encoding="utf-8") as f:
    for img in images_data:
        f.write(f"Файл: {img['image_name']} | URL: {img['url']}\n")

# У формат CSV
with open("images_list.csv", "w", newline="", encoding="utf-8") as csv_file:
    writer = csv.DictWriter(csv_file, fieldnames=["image_name", "url", "local_path"])
    writer.writeheader()
    writer.writerows(images_data)

print("Дані зображень збережено у файли: images_list.txt, images_list.csv та папку 'images/'")


# 6 ЗБЕРЕЖЕННЯ ДАНИХ ДО БАЗИ ДАНИХ (SQLite)
print("\n--- КРОК 6: Збереження даних до бази даних SQLite ---")
db_conn = sqlite3.connect("database.db")
cursor = db_conn.cursor()

# Створення таблиць
cursor.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    url TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT,
    title TEXT,
    url TEXT,
    price TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_name TEXT,
    url TEXT,
    local_path TEXT
)
""")

# Заповнення таблиці категорій
for cat in categories_data:
    cursor.execute("INSERT INTO categories (name, url) VALUES (?, ?)", (cat["name"], cat["url"]))

# Заповнення таблиці книжок
for book in all_books:
    cursor.execute("INSERT INTO books (category_name, title, url, price) VALUES (?, ?, ?, ?)",
                   (book["category"], book["title"], resource_or_url := book["url"], book["price"]))

# Заповнення таблиці зображень
for img in images_data:
    cursor.execute("INSERT INTO images (image_name, url, local_path) VALUES (?, ?, ?)",
                   (img["image_name"], img["url"], img["local_path"]))

db_conn.commit()
db_conn.close()

print("Усі дані успішно збережено до бази даних SQLite ('database.db')!")