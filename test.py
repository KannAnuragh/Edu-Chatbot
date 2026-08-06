from libindic.payyans import Payyans

# 1. Initialize Payyans
p = Payyans()
print("Installed Payyans Maps:")
print(p.listAvailableMaps())
print("=" * 60)

# 2. Raw FML ASCII Chunk from SCERT PDF
raw_chunk = """kmaqlyimkv{Xw I X Ãm≥tU¿Uv temIw Ccp-]Xmw \q‰m-≠n¬ 35 H∂mw temIbp≤-Øns‚ sISpXn A\p-`-hn-°mØ cmPy-am-bn-cp∂p Ata-cn-°."""

print("\n--- Testing Map Outputs ---")
for m in p.listAvailableMaps():
    try:
        res = p.ASCII2Unicode(raw_chunk, m)
        print(f"[{m}]:\n{res}\n")
    except Exception as e:
        print(f"[{m}]: FAILED -> {e}\n")
