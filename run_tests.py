"""Run all test suites"""
import subprocess, sys, os

base = os.path.dirname(os.path.abspath(__file__))
tests = ["test_app.py", "test_integration.py", "test_ocr_simulasyon.py"]
all_ok = True

for t in tests:
    path = os.path.join(base, t)
    if not os.path.exists(path):
        print(f"[SKIP] {t} (dosya yok)")
        continue
    print(f"\n=== {t} ===")
    r = subprocess.run([sys.executable, "-W", "ignore", path], capture_output=True, text=True, cwd=base)
    # Print only relevant lines
    for line in r.stdout.splitlines():
        if any(x in line for x in ["[PASS]", "[FAIL]", "[SKIP]", "===", "TUM", "basari", "ERROR", "HATA"]):
            print(line)
    if r.returncode != 0:
        print(f"[FAIL] {t} cikis kodu: {r.returncode}")
        if r.stderr:
            for line in r.stderr.splitlines()[-5:]:
                print(f"  {line}")
        all_ok = False

print(f"\n{'='*40}")
print(f"SONUC: {'TUM TESTLER BASARILI' if all_ok else 'BAZI TESTLER BASARISIZ'}")
print(f"{'='*40}")
