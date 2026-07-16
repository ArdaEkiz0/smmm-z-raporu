"""
Kullanici yonetimi modulu.
- SHA-256 sifre hash'leme
- Kullanici ekleme/silme/listeleme
- Rol kontrolu (admin, user)
- Eski tek-sifre formatini yeni cok-kullanici formatina migrate
"""
import hashlib
import json
import os
import secrets
from typing import List, Dict, Optional

from config import AUTH_FILE
from utils import dosya_oku, dosya_yaz, log


ROLES = ["admin", "user"]
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"


def _hash_sifre(sifre: str, salt: str = "") -> str:
    """SHA-256 ile sifre hash'le. Salt opsiyonel (guvenlik artisi)."""
    if not sifre:
        return ""
    if salt:
        return hashlib.sha256(f"{salt}{sifre}".encode("utf-8")).hexdigest()
    return hashlib.sha256(sifre.encode("utf-8")).hexdigest()


def _kullanici_default_admin() -> Dict:
    """Ilk kurulum icin default admin kullanici."""
    return {
        "username": DEFAULT_ADMIN_USERNAME,
        "password_hash": _hash_sifre(DEFAULT_ADMIN_PASSWORD),
        "role": "admin",
        "full_name": "Sistem Yöneticisi",
        "email": "",
        "aktif": True,
        "olusturma": "2026-01-01",
    }


def kullanicilari_yukle() -> List[Dict]:
    """Tum kullanicilari yukle. Dosya yoksa veya eski formatta ise migrate et."""
    if not os.path.exists(AUTH_FILE):
        return _ilk_kurulum_olustur()

    try:
        data = dosya_oku(AUTH_FILE, {})
    except Exception as e:
        log.warning(f"AUTH_FILE okunamadi, yenisi olusturuluyor: {e}")
        return _ilk_kurulum_olustur()

    if not data:
        return _ilk_kurulum_olustur()

    if "users" in data and isinstance(data["users"], list):
        return data["users"]

    if "passwords" in data and isinstance(data["passwords"], list):
        return _eski_format_migrate(data["passwords"])

    return _ilk_kurulum_olustur()


def _ilk_kurulum_olustur() -> List[Dict]:
    """Ilk kurulum: default admin olustur ve kaydet."""
    admin = _kullanici_default_admin()
    kullanicilar = [admin]
    _kaydet(kullanicilar)
    log.info(f"Ilk kurulum: default admin '{DEFAULT_ADMIN_USERNAME}' olusturuldu")
    return kullanicilar


def _eski_format_migrate(eski_passwords: list) -> List[Dict]:
    """Eski {passwords: [...]} formatini yeni formata cevir.
    Tum sifreler tek bir 'admin' kullanicisina atanir, ardindan sifre degistirilmesi gerekir.
    """
    kullanicilar = []
    for idx, eski_sifre in enumerate(eski_passwords):
        if isinstance(eski_sifre, str):
            plain = eski_sifre
        elif isinstance(eski_sifre, str) and eski_sifre.startswith("sha256:"):
            plain = None
        else:
            plain = None

        username = DEFAULT_ADMIN_USERNAME if idx == 0 else f"user{idx}"
        role = "admin" if idx == 0 else "user"

        kullanicilar.append({
            "username": username,
            "password_hash": _hash_sifre(plain) if plain else eski_sifre.replace("sha256:", "") if isinstance(eski_sifre, str) and eski_sifre.startswith("sha256:") else "",
            "role": role,
            "full_name": f"Kullanici {idx + 1}",
            "email": "",
            "aktif": True,
            "olusturma": "2026-01-01",
        })

    _kaydet(kullanicilar)
    log.info(f"Eski format migrate edildi: {len(kullanicilar)} kullanici olusturuldu")
    return kullanicilar


def _kaydet(kullanicilar: List[Dict]):
    """Kullanicilari dosyaya kaydet."""
    data = {"users": kullanicilar}
    dosya_yaz(AUTH_FILE, data)


def kullanici_bul(username: str) -> Optional[Dict]:
    """Kullanici adina gore kullanici bul."""
    kullanicilar = kullanicilari_yukle()
    for k in kullanicilar:
        if k.get("username", "").lower() == (username or "").lower():
            return k
    return None


def kullanici_dogrula(username: str, sifre: str) -> Optional[Dict]:
    """Kullanici adi + sifre dogrula. Basariliysa kullanici doner, yoksa None."""
    if not username or not sifre:
        return None
    k = kullanici_bul(username)
    if not k:
        return None
    if not k.get("aktif", True):
        return None
    stored = k.get("password_hash", "")
    if not stored:
        return None
    return k if _hash_sifre(sifre) == stored else None


def kullanici_ekle(username: str, sifre: str, role: str = "user", full_name: str = "",
                   email: str = "") -> Dict:
    """Yeni kullanici ekle. {basarili: bool, mesaj: str} doner."""
    if not username or not sifre:
        return {"basarili": False, "mesaj": "Kullanıcı adı ve şifre gerekli"}
    if role not in ROLES:
        return {"basarili": False, "mesaj": f"Geçersiz rol. Geçerli: {ROLES}"}
    if kullanici_bul(username):
        return {"basarili": False, "mesaj": "Bu kullanıcı adı zaten mevcut"}
    if len(sifre) < 4:
        return {"basarili": False, "mesaj": "Şifre en az 4 karakter olmalı"}

    from datetime import datetime
    kullanicilar = kullanicilari_yukle()
    yeni = {
        "username": username,
        "password_hash": _hash_sifre(sifre),
        "role": role,
        "full_name": full_name or username,
        "email": email,
        "aktif": True,
        "olusturma": datetime.now().strftime("%Y-%m-%d"),
    }
    kullanicilar.append(yeni)
    _kaydet(kullanicilar)
    return {"basarili": True, "mesaj": f"Kullanıcı '{username}' eklendi"}


def kullanici_sil(username: str) -> Dict:
    """Kullanici sil. Admin kendini silemez."""
    if username == DEFAULT_ADMIN_USERNAME:
        return {"basarili": False, "mesaj": "Default admin silinemez"}
    kullanicilar = kullanicilari_yukle()
    yeni_liste = [k for k in kullanicilar if k.get("username", "").lower() != username.lower()]
    if len(yeni_liste) == len(kullanicilar):
        return {"basarili": False, "mesaj": "Kullanıcı bulunamadı"}
    _kaydet(yeni_liste)
    return {"basarili": True, "mesaj": f"Kullanıcı '{username}' silindi"}


def kullanici_sifre_degistir(username: str, eski_sifre: str, yeni_sifre: str) -> Dict:
    """Kullanici sifresini degistir."""
    if not kullanici_dogrula(username, eski_sifre):
        return {"basarili": False, "mesaj": "Mevcut şifre yanlış"}
    if len(yeni_sifre) < 4:
        return {"basarili": False, "mesaj": "Yeni şifre en az 4 karakter olmalı"}
    kullanicilar = kullanicilari_yukle()
    for k in kullanicilar:
        if k.get("username", "").lower() == username.lower():
            k["password_hash"] = _hash_sifre(yeni_sifre)
            break
    _kaydet(kullanicilar)
    return {"basarili": True, "mesaj": "Şifre güncellendi"}


def kullanici_admin_mi(username: str) -> bool:
    """Kullanici admin mi?"""
    k = kullanici_bul(username)
    return bool(k and k.get("role") == "admin")


def kullanici_listesi_safe() -> List[Dict]:
    """Sifre hash'leri olmadan kullanici listesi (UI icin)."""
    kullanicilar = kullanicilari_yukle()
    safe = []
    for k in kullanicilar:
        s = {kk: vv for kk, vv in k.items() if kk != "password_hash"}
        s["password_gizli"] = "•" * 8
        safe.append(s)
    return safe


def sifre_hash_al(sifre: str) -> str:
    """Disaridan hash alma (UI olusturma sirasinda)."""
    return _hash_sifre(sifre)
