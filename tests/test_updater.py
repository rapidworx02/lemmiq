from pathlib import Path
import tempfile
import unittest
import importlib.util

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v212_installer',BASE/'APPLY_V2.12.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)

class V212UpdaterTests(unittest.TestCase):
    def make_repo(self, root: Path):
        files={
          'backend/app/v28.py':'# wallet unchanged\n',
          'backend/app/main.py': '''app = FastAPI(title="LEMMIQ Server", version="2.10.10")
@app.get("/health")
def health():return {"version": "2.10.10", "ok": True}
@app.get("/app-config")
def app_config():return {"version": "2.10.10", "ok": True}
# ---------------- LEMMIQ V2 WEB / PWA ----------------
''',
          'backend/app/v2105_q_features.py': '''FEATURES = {
    "Q_VISION": "Q Vision",
}
DEFAULT_GLOBAL_Q = {
    "Q_VISION": 2.00,
}
''',
          'backend/web/index.html':'<html><head></head><body></body></html>',
          'backend/web/sw.js': '''const CACHE = "lemmiq-v21010-shell-1";
const SHELL = [
  "/web/manifest.webmanifest",
];
const API_PREFIXES=["/v29"];
''',
          'android/app/build.gradle.kts':'''android {
 versionCode=61
 versionName="2.10.11"
}
''',
          'android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt': '''    val c=vm.active?:return
    var settings by remember{mutableStateOf(false)}
    var showVisionHistory by remember{mutableStateOf(false)}
    val qChargingOn=vm.qFeatureCatalog.any{it.charging_enabled}
        item{
            val pending=vm.qHome?.q_to_q?.pending_count ?: 0
        }
                                 TextButton({videoPicker.launch("video/*");showAttach=false}){Text("🎬 Video")}
    vm.chatSummary?.let{s->ChatSummaryDialog(s){vm.clearChatSummary()}}
''',
        }
        for k,v in files.items():
            dest=root/k;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(v,encoding='utf-8')

    def test_dry_run_apply_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_repo(root)
            wallet=(root/'backend/app/v28.py').read_bytes()
            changes=updater.prepare(root)
            self.assertEqual(len(changes),10)
            self.assertFalse((root/'backend/app/v212_image_gen.py').exists())
            backup=updater.apply(root,changes)
            self.assertTrue(backup.exists())
            self.assertEqual(wallet,(root/'backend/app/v28.py').read_bytes())
            self.assertIn('register_v212_images', (root/'backend/app/main.py').read_text())
            self.assertIn('"Q_IMAGE": 0.00',(root/'backend/app/v2105_q_features.py').read_text())
            self.assertIn('Q Create Image',(root/'android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt').read_text())
            self.assertEqual({}, updater.prepare(root))

    def test_fail_closed_when_android_anchor_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_repo(root)
            ui=root/'android/app/src/main/java/com/lemmiq/app/LemmiqApp.kt'
            original=ui.read_text().replace('var showVisionHistory','var someOtherState')
            ui.write_text(original)
            with self.assertRaises(updater.Incompatible):updater.prepare(root)
            self.assertFalse((root/'backend/app/v212_image_gen.py').exists())

    def test_no_code_downgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.make_repo(root)
            f=root/'android/app/build.gradle.kts'
            f.write_text(f.read_text().replace('versionCode=61','versionCode=88'))
            with self.assertRaises(updater.Incompatible):updater.prepare(root)

if __name__=='__main__':unittest.main()
