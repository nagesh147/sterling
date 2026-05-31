import sys
import glob

files = [
    "frontend/src/components/derivatives/FuturesCandidatesTable.tsx",
    "frontend/src/components/derivatives/OptionsCandidatesTable.tsx",
    "frontend/src/components/derivatives/DerivativesCandidatesTable.tsx"
]

for filepath in files:
    try:
        with open(filepath, "r") as f:
            content = f.read()

        new_catch = """    } catch (err) {
      const msg = (err as Error)?.message || String(err);
      
      let parsed = msg;
      let isLocked = false;
      try {
        const obj = JSON.parse(msg);
        if (obj.code === 'daily_loss_halt' || obj.error?.includes('Daily loss')) isLocked = true;
        parsed = obj.error || obj.reason || obj.code || msg;
      } catch (e) {
        // Not JSON
        if (msg.includes('daily_loss_halt')) isLocked = true;
      }

      if (parsed.includes('stale_candidate') || parsed.includes('409') || parsed.includes('freeze_token')) {
        setToast('✗ Candidates refreshed — re-confirm (Stale 409)');
      } else if (isLocked || parsed.includes('Locked') || parsed.includes('423')) {
        setToast(`🔒 LOCKED: ${parsed}`);
      } else {
        setToast(`✗ ${parsed}`);
      }
      refetch();
    }"""
        
        import re
        content = re.sub(r'\} catch \(err\) \{.*?\n\s+refetch\(\);\n\s+\}', new_catch, content, flags=re.DOTALL)

        with open(filepath, "w") as f:
            f.write(content)
        print(f"Patched {filepath}")
    except Exception as e:
        print(f"Failed to patch {filepath}: {e}")

