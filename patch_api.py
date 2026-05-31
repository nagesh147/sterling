import sys

filepath = "frontend/src/utils/api.ts"
with open(filepath, "r") as f:
    content = f.read()

content = content.replace(
    "throw new Error((err as { detail?: string }).detail ?? `HTTP ${resp.status}`);",
    """let msg = `HTTP ${resp.status}`;
    if (err && typeof err === 'object' && 'detail' in err) {
      if (typeof err.detail === 'string') {
        msg = err.detail;
      } else if (typeof err.detail === 'object' && err.detail !== null) {
        msg = JSON.stringify(err.detail);
      }
    }
    throw new Error(msg);"""
)

with open(filepath, "w") as f:
    f.write(content)
print("Patched api.ts")
