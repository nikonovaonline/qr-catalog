import os
from dotenv import load_dotenv
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
import qrcode
import boto3
from botocore.client import Config

# === Конфигурация ===
load_dotenv()
YC_KEY_ID = os.getenv('YC_KEY_ID')
YC_KEY_SECRET = os.getenv('YC_KEY_SECRET')
BUCKET_NAME = os.getenv('BUCKET_NAME')
BASE_URL = os.getenv('BASE_URL', f'https://storage.yandexcloud.net/{BUCKET_NAME}')
if not all([YC_KEY_ID, YC_KEY_SECRET, BUCKET_NAME]):
    raise EnvironmentError("Set YC_KEY_ID, YC_KEY_SECRET and BUCKET_NAME in .env or env vars")

# Пути и директории
INPUT_FILE = 'products.xlsx'  # Объединённая таблица с нужными колонками
OUTPUT_DIR = 'output'
QRCODES_DIR = os.path.join(OUTPUT_DIR, 'qrcodes')
HTML_DIR = os.path.join(OUTPUT_DIR, 'html')
TEMPLATES_DIR = 'templates'

os.makedirs(QRCODES_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

# === Инициализация S3-клиента ===
s3 = boto3.client(
    's3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=YC_KEY_ID,
    aws_secret_access_key=YC_KEY_SECRET,
    config=Config(signature_version='s3v4')
)

# === Загрузка и подготовка данных ===
def load_data(path: str) -> pd.DataFrame:
    # Читаем первую строку как заголовки
    df = pd.read_excel(path, dtype=str)
    # Удаляем колонки без названия
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    # Заменяем NaN на пустые строки
    df = df.fillna('')
    return df

# === Генерация QR-кода ===
def generate_qr_code(url: str, out_path: str):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(out_path)

# === Настройка шаблонизатора ===
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(['html', 'xml'])
)
template = env.get_template('card.html')

def render_html(item: dict, columns: list, qr_file: str) -> str:
    return template.render(
        item=item,
        columns=columns,
        qr_image=qr_file
    )

# === Загрузка в бакет ===
def upload_to_bucket(src_path: str, object_name: str, content_type: str):
    with open(src_path, 'rb') as f:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=object_name,
            Body=f.read(),
            ContentType=content_type,
            ACL='public-read'
        )

# === Основной процесс ===
def main():
    df = load_data(INPUT_FILE)
    columns = list(df.columns)
    print(f"Loaded {len(df)} rows with columns: {columns}")

    for idx, row in df.iterrows():
        key = f"item_{idx+1}"
        html_file = f"{key}.html"
        qr_file = f"{key}.png"
        html_path = os.path.join(HTML_DIR, html_file)
        qr_path = os.path.join(QRCODES_DIR, qr_file)

        # Генерация QR и страницы
        url = f"{BASE_URL}/{html_file}"
        generate_qr_code(url, qr_path)
        item = row.to_dict()
        html_content = render_html(item, columns, qr_file)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # Загрузка
        upload_to_bucket(html_path, html_file, 'text/html; charset=utf-8')
        upload_to_bucket(qr_path, f"qrcodes/{qr_file}", 'image/png')
        print(f"Uploaded {key}")

    print("All cards generated and uploaded.")

if __name__ == '__main__':
    main()
