using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("MP3 Score Portable")]
[assembly: System.Reflection.AssemblyProduct("MP3 악보 포터블")]
[assembly: System.Reflection.AssemblyVersion("0.1.2.0")]

static class Program
{
    internal static readonly string Root = AppDomain.CurrentDomain.BaseDirectory;
    internal static readonly string Data = Path.Combine(Root, "portable-data");
    internal static readonly string Ready = Path.Combine(Data, "server.ready");
    internal static readonly string StopFile = Path.Combine(Data, "stop.request");

    internal static string ReadUrl(int expectedPid)
    {
        try
        {
            string[] lines = File.ReadAllLines(Ready, Encoding.UTF8);
            int pid;
            Uri uri;
            if (lines.Length < 2 || !Int32.TryParse(lines[0], out pid)) return null;
            if (expectedPid != 0 && pid != expectedPid) return null;
            if (Process.GetProcessById(pid).HasExited) return null;
            if (!Uri.TryCreate(lines[1], UriKind.Absolute, out uri)) return null;
            if (uri.Scheme != "http" || uri.Host != "127.0.0.1" || uri.AbsolutePath != "/") return null;
            return uri.AbsoluteUri;
        }
        catch { return null; }
    }

    static readonly object LogLock = new object();

    internal static void LauncherLog(string line)
    {
        if (line == null) return;
        try
        {
            lock (LogLock)
            {
                string logs = Path.Combine(Data, "logs");
                Directory.CreateDirectory(logs);
                File.AppendAllText(Path.Combine(logs, "launcher.log"), line + Environment.NewLine, Encoding.UTF8);
            }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }

    static string Tail(string file)
    {
        try
        {
            string text = File.ReadAllText(file, Encoding.UTF8);
            return text.Length > 7000 ? text.Substring(text.Length - 7000) : text;
        }
        catch { return "(로그 없음)"; }
    }

    internal static void ShowIssue(string message)
    {
        string logs = Path.Combine(Data, "logs");
        string detail = message + "\r\n\r\n오류 요약:\r\n" + Tail(Path.Combine(logs, "error-summary.txt"))
            + "\r\n\r\n실행 폴더: " + Root + "\r\n\r\n서버 로그:\r\n" + Tail(Path.Combine(logs, "server.log"))
            + "\r\n\r\n초기 실행 로그:\r\n" + Tail(Path.Combine(logs, "launcher.log"));
        using (Form dialog = new Form())
        {
            dialog.Text = "MP3 악보 포터블 · 실행 오류 상세";
            dialog.Size = new Size(860, 540);
            dialog.StartPosition = FormStartPosition.CenterScreen;
            TextBox text = new TextBox();
            text.Multiline = true;
            text.ReadOnly = true;
            text.ScrollBars = ScrollBars.Both;
            text.WordWrap = false;
            text.Dock = DockStyle.Fill;
            text.Font = new Font("Consolas", 10);
            text.Text = detail;
            FlowLayoutPanel buttons = new FlowLayoutPanel();
            buttons.Height = 48;
            buttons.Dock = DockStyle.Bottom;
            Button copy = new Button(); copy.Text = "오류 복사"; copy.Width = 110;
            copy.Click += delegate { Clipboard.SetText(detail); };
            Button folder = new Button(); folder.Text = "로그 폴더 열기"; folder.Width = 140;
            folder.Click += delegate { if (Directory.Exists(logs)) Process.Start(new ProcessStartInfo(logs) { UseShellExecute = true }); };
            Button close = new Button(); close.Text = "닫기"; close.Width = 90; close.DialogResult = DialogResult.OK;
            buttons.Controls.Add(copy); buttons.Controls.Add(folder); buttons.Controls.Add(close);
            dialog.Controls.Add(text); dialog.Controls.Add(buttons);
            dialog.AcceptButton = close;
            dialog.ShowDialog();
        }
    }

    internal static void OpenBrowser(string url)
    {
        if (url == null) return;
        try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
        catch (Exception ex) { ShowIssue("기본 브라우저를 열지 못했습니다. 아래 주소를 직접 열어도 됩니다.\r\n" + url + "\r\n" + ex.Message); }
    }

    [STAThread]
    static void Main(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool stop = Array.IndexOf(args, "--stop") >= 0;
        bool noBrowser = Array.IndexOf(args, "--no-browser") >= 0;
        if (stop)
        {
            if (ReadUrl(0) != null) File.WriteAllText(StopFile, "stop", Encoding.UTF8);
            return;
        }
        string key;
        using (SHA256 hash = SHA256.Create())
            key = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(Root.ToUpperInvariant()))).Replace("-", "");
        using (Mutex mutex = new Mutex(false, @"Local\MP3ScorePortable_" + key))
        {
            bool owned = false;
            try
            {
                try { owned = mutex.WaitOne(0, false); }
                catch (AbandonedMutexException) { owned = true; }
                if (!owned)
                {
                    string url = ReadUrl(0);
                    if (url != null && !noBrowser) OpenBrowser(url);
                    else if (!noBrowser) MessageBox.Show("프로그램이 이미 시작 중입니다. 잠시 기다려 주세요.", "MP3 악보 포터블");
                    return;
                }
                Application.Run(new PortableContext(noBrowser));
            }
            catch (Exception ex)
            {
                MessageBox.Show("시작하지 못했습니다. 압축을 완전히 풀고, 쓰기 가능한 폴더에서 실행하세요.\n\n" + ex.Message,
                                "MP3 악보 포터블", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            finally { if (owned) mutex.ReleaseMutex(); }
        }
    }
}

sealed class PortableContext : ApplicationContext
{
    readonly NotifyIcon tray;
    readonly System.Windows.Forms.Timer timer;
    readonly Process child;
    readonly bool noBrowser;
    readonly DateTime started = DateTime.UtcNow;
    bool opened;
    bool stopping;
    string url;

    internal PortableContext(bool silent)
    {
        noBrowser = silent;
        string python = Path.Combine(Program.Root, "runtime", "python.exe");
        string launcher = Path.Combine(Program.Root, "portable_launcher.py");
        if (!File.Exists(python) || !File.Exists(launcher)) throw new FileNotFoundException("runtime 폴더 또는 실행 파일이 없습니다.");
        Directory.CreateDirectory(Program.Data);
        if (File.Exists(Program.Ready)) File.Delete(Program.Ready);
        if (File.Exists(Program.StopFile)) File.Delete(Program.StopFile);
        ProcessStartInfo info = new ProcessStartInfo(python, "\"" + launcher + "\" --parent-pid " + Process.GetCurrentProcess().Id);
        info.WorkingDirectory = Program.Root;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        foreach (string key in new string[] { "PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PIP_PREFIX", "PIP_TARGET" })
            info.EnvironmentVariables.Remove(key);
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.RedirectStandardOutput = true;
        info.RedirectStandardError = true;
        info.StandardOutputEncoding = Encoding.UTF8;
        info.StandardErrorEncoding = Encoding.UTF8;
        child = new Process();
        child.StartInfo = info;
        child.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { Program.LauncherLog(e.Data); };
        child.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { Program.LauncherLog(e.Data); };
        child.Start();
        child.BeginOutputReadLine();
        child.BeginErrorReadLine();
        tray = new NotifyIcon();
        tray.Icon = SystemIcons.Application;
        tray.Text = "MP3 악보 포터블: 시작 중";
        ContextMenuStrip menu = new ContextMenuStrip();
        menu.Items.Add("악보 화면 열기", null, delegate { Program.OpenBrowser(url); });
        menu.Items.Add("프로그램 종료", null, delegate { RequestStop(); });
        tray.ContextMenuStrip = menu;
        tray.DoubleClick += delegate { Program.OpenBrowser(url); };
        tray.Visible = true;
        timer = new System.Windows.Forms.Timer();
        timer.Interval = 700;
        timer.Tick += Tick;
        timer.Start();
    }

    void RequestStop()
    {
        stopping = true;
        tray.Text = "MP3 악보 포터블: 작업 완료 후 종료 중";
        File.WriteAllText(Program.StopFile, "stop", Encoding.UTF8);
    }

    void Tick(object sender, EventArgs e)
    {
        if (child.HasExited)
        {
            timer.Stop();
            tray.Visible = false;
            tray.Dispose();
            timer.Dispose();
            child.WaitForExit();
            if (child.ExitCode != 0 && !stopping)
                Program.ShowIssue("프로그램이 종료되었습니다. 종료 코드: " + child.ExitCode + "\r\n아래 원인과 로그를 확인하세요.");
            child.Dispose();
            ExitThread();
            return;
        }
        if (opened || stopping) return;
        string candidate = Program.ReadUrl(child.Id);
        if (candidate != null)
        {
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(candidate + "api/info");
                request.Proxy = null;
                request.Timeout = 700;
                using (HttpWebResponse response = (HttpWebResponse)request.GetResponse())
                    if (response.StatusCode != HttpStatusCode.OK) return;
                url = candidate;
                opened = true;
                tray.Text = "MP3 악보 포터블";
                if (!noBrowser) Program.OpenBrowser(url);
            }
            catch (WebException) { }
        }
        if (!opened && (DateTime.UtcNow - started).TotalSeconds > 180)
        {
            RequestStop();
            Program.ShowIssue("시작 시간이 초과되었습니다. 아래 로그를 확인하세요.");
        }
    }
}
