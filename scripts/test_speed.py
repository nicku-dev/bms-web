import json
import time
from app.compiler import FastMatrixCompiler

def run_test():
    with open('../bms-reporting/debug_matrix.json', 'r') as f:
        matrix = json.load(f)

    print("Memulai kompilasi Skenario 1 (DuckDB)...")
    start = time.time()
    
    compiler = FastMatrixCompiler('BMS_26_PRODUCTION', 2025, 'fps')
    matrix_result = compiler.compile(matrix)
    
    end = time.time()
    
    # Hitung jumlah tag yang berhasil dieksekusi dari cache internal
    tags_count = len(compiler.cache)
    
    print(f"Selesai dalam: {(end - start):.4f} detik")
    print(f"Jumlah Tag/Query yang dieksekusi: {tags_count}")

if __name__ == "__main__":
    run_test()
