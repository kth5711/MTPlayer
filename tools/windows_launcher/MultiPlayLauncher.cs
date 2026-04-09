using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class MultiPlayLauncher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string launcherPath = Application.ExecutablePath;
            Process currentProcess = Process.GetCurrentProcess();
            if (currentProcess != null && currentProcess.MainModule != null && !string.IsNullOrEmpty(currentProcess.MainModule.FileName))
            {
                launcherPath = currentProcess.MainModule.FileName;
            }

            string root = Path.GetDirectoryName(launcherPath);
            if (string.IsNullOrEmpty(root))
            {
                root = AppDomain.CurrentDomain.BaseDirectory;
            }
            string vbsLauncher = Path.Combine(root, "run_multi_play.vbs");
            string batLauncher = Path.Combine(root, "run_multi_play.bat");
            string appMain = Path.Combine(root, "app", "main.py");
            string pythonw = Path.Combine(root, "pythonw.exe");
            string python = Path.Combine(root, "python.exe");

            if (File.Exists(vbsLauncher))
            {
                StartDetached("wscript.exe", string.Format("//nologo \"{0}\"", vbsLauncher));
                return 0;
            }

            if (File.Exists(batLauncher))
            {
                StartDetached("cmd.exe", string.Format("/c \"{0}\"", batLauncher));
                return 0;
            }

            if (File.Exists(appMain))
            {
                if (File.Exists(pythonw))
                {
                    StartDetached(pythonw, string.Format("\"{0}\"", appMain));
                    return 0;
                }

                if (File.Exists(python))
                {
                    StartDetached(python, string.Format("\"{0}\"", appMain));
                    return 0;
                }
            }

            MessageBox.Show(
                "Could not find a launcher.\n\nExpected one of:\n- run_multi_play.vbs\n- run_multi_play.bat\n- python(.exe) + app\\\\main.py",
                "MTPlayer",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.ToString(),
                "MTPlayer",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }
    }

    private static void StartDetached(string fileName, string arguments)
    {
        var psi = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden,
            WorkingDirectory = AppDomain.CurrentDomain.BaseDirectory,
        };
        Process.Start(psi);
    }
}
