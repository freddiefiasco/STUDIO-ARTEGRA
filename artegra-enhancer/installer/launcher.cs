// Windows entry points for the official, unpacked Python distribution.
// Compile as winexe for the desktop app; define SETUP_WORKER for the helper.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
#if SETUP_WORKER
using System.Runtime.InteropServices;
using System.Threading;
#else
using System.Windows.Forms;
#endif

internal static class ArtegraLauncher
{
    // Windows C runtime argument convention: quote empty values and double
    // backslashes before quotes and before the closing delimiter.
    internal static string QuoteArgument(string value)
    {
        StringBuilder result = new StringBuilder("\"");
        int backslashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { backslashes++; continue; }
            if (character == '"')
            {
                result.Append('\\', backslashes * 2 + 1);
                result.Append('"');
            }
            else
            {
                result.Append('\\', backslashes);
                result.Append(character);
            }
            backslashes = 0;
        }
        result.Append('\\', backslashes * 2);
        result.Append('"');
        return result.ToString();
    }

#if SETUP_WORKER
    // Query-only parent discovery, without WMI or an additional dependency.
    // PROCESS_BASIC_INFORMATION includes InheritedFromUniqueProcessId.
    [StructLayout(LayoutKind.Sequential)]
    private struct ProcessBasicInformation
    {
        public IntPtr Reserved1, PebBaseAddress, Reserved2a, Reserved2b;
        public IntPtr UniqueProcessId, InheritedFromUniqueProcessId;
    }
    [DllImport("ntdll.dll")]
    private static extern int NtQueryInformationProcess(IntPtr process, int informationClass,
        out ProcessBasicInformation information, int size, out int returnedSize);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);
    [DllImport("kernel32.dll")]
    private static extern bool CloseHandle(IntPtr handle);

    private static IntPtr OpenInstallerParent()
    {
        ProcessBasicInformation information;
        int returnedSize;
        using (Process current = Process.GetCurrentProcess())
        {
            int status = NtQueryInformationProcess(current.Handle, 0, out information,
                Marshal.SizeOf(typeof(ProcessBasicInformation)), out returnedSize);
            if (status != 0) throw new InvalidOperationException("Could not monitor setup.");
        }
        uint parentId = checked((uint)information.InheritedFromUniqueProcessId.ToInt64());
        IntPtr handle = OpenProcess(0x00100000, false, parentId); // SYNCHRONIZE only
        if (handle == IntPtr.Zero) throw new InvalidOperationException("Setup has closed.");
        return handle;
    }
#endif

    [STAThread]
    private static int Main(string[] arguments)
    {
#if SETUP_WORKER
        const string module = "host.setup_cli";
        const string interpreterName = "python.exe";
        IntPtr installerParent = IntPtr.Zero;
        ManualResetEvent finished = new ManualResetEvent(false);
        Thread parentWatcher = null;
#else
        const string module = "host.app";
        const string interpreterName = "pythonw.exe";
        bool quiet = Array.IndexOf(arguments, "--smoke") >= 0;
#endif
        try
        {
            string root = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
#if SETUP_WORKER
            root = Directory.GetParent(root).FullName;
            Console.OutputEncoding = new UTF8Encoding(false);
#endif
            string interpreter = Path.Combine(root, "desktop-runtime", interpreterName);
            string entry = Path.Combine(root, "host", module == "host.app" ? "app.py" : "setup_cli.py");
            if (!File.Exists(interpreter) || !File.Exists(entry))
                throw new FileNotFoundException("Required application files are missing.");

            StringBuilder command = new StringBuilder("-I -X utf8 -S -B -m ");
            command.Append(QuoteArgument(module));
            foreach (string argument in arguments)
            {
                command.Append(' ');
                command.Append(QuoteArgument(argument));
            }
            ProcessStartInfo start = new ProcessStartInfo(interpreter, command.ToString());
            start.UseShellExecute = false;
            start.CreateNoWindow = true;
            start.WorkingDirectory = root;
            start.EnvironmentVariables.Remove("PYTHONHOME");
            start.EnvironmentVariables.Remove("PYTHONPATH");
            start.EnvironmentVariables.Remove("QT_PLUGIN_PATH");
            start.EnvironmentVariables.Remove("QT_QPA_PLATFORM_PLUGIN_PATH");
            start.EnvironmentVariables.Remove("QML2_IMPORT_PATH");
            start.EnvironmentVariables.Remove("QML_IMPORT_PATH");
            start.EnvironmentVariables["PATH"] = String.Join(Path.PathSeparator.ToString(), new string[] {
                Path.Combine(root, "desktop-runtime"),
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                Environment.GetFolderPath(Environment.SpecialFolder.Windows)
            });
#if SETUP_WORKER
            installerParent = OpenInstallerParent();
            start.RedirectStandardOutput = true;
            start.RedirectStandardError = true;
            start.StandardOutputEncoding = new UTF8Encoding(false);
            start.StandardErrorEncoding = new UTF8Encoding(false);
#endif
            using (Process child = new Process())
            {
                child.StartInfo = start;
#if SETUP_WORKER
                child.OutputDataReceived += delegate(object sender, DataReceivedEventArgs data)
                {
                    try { if (data.Data != null) Console.Out.WriteLine(data.Data); }
                    catch (IOException) { }
                };
                child.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs data)
                {
                    try { if (data.Data != null) Console.Error.WriteLine(data.Data); }
                    catch (IOException) { }
                };
#endif
                if (!child.Start()) throw new InvalidOperationException("Windows did not start the application.");
#if SETUP_WORKER
                child.BeginOutputReadLine();
                child.BeginErrorReadLine();
                parentWatcher = new Thread(delegate()
                {
                    while (!finished.WaitOne(100))
                    {
                        uint status = WaitForSingleObject(installerParent, 0);
                        // Exiting this wrapper lets setup_cli's existing parent
                        // watcher cancel its own downloads and owned processes.
                        if (status == 0 || status == 0xFFFFFFFF) Environment.Exit(130);
                    }
                });
                parentWatcher.IsBackground = true;
                parentWatcher.Start();
#endif
                child.WaitForExit();
                int result = child.ExitCode;
#if !SETUP_WORKER
                if (result != 0 && !quiet) ShowFailure();
#endif
                return result;
            }
        }
        catch (Exception)
        {
#if SETUP_WORKER
            Console.Out.WriteLine("ARTEGRA-ERROR|Windows could not start setup. Reopen the installer to repair the application. Your downloaded files have been kept.");
#else
            if (!quiet) ShowFailure();
#endif
            return 1;
        }
#if SETUP_WORKER
        finally
        {
            finished.Set();
            if (parentWatcher != null) parentWatcher.Join(1000);
            if (installerParent != IntPtr.Zero) CloseHandle(installerParent);
            finished.Dispose();
        }
#endif
    }

#if !SETUP_WORKER
    private static void ShowFailure()
    {
        MessageBox.Show("Artegra Enhancer could not start. Reopen the installer to repair the application. Your images and enhancement files will be kept.",
                        "Artegra Enhancer", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }
#endif
}
