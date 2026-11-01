' ============================================
'  UNI MATE - chạy NGẦM (ẩn cửa sổ cmd)
'  Double-click file này (hoặc start-unimate.bat) để bật server ở chế độ nền.
'  Log ghi vào server\unimate.log. Dừng bằng stop-unimate.bat.
' ============================================
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
Set sh = CreateObject("WScript.Shell")

' QUAN TRỌNG: mọi lệnh đều cd /d vào root trước - KHÔNG dựa vào working directory
' kế thừa (CurrentDirectory không đáng tin tuỳ nơi gọi, từng làm bước stop chết
' im lặng với lỗi 'stop-unimate.bat is not recognized').

' Tắt instance cũ trước (ẩn, chờ xong). Output ghi server\stop-last.log để soi khi trục trặc.
' GỌI BẰNG ĐƯỜNG DẪN TUYỆT ĐỐI: tên trần "stop-unimate.bat" bị cmd từ chối tìm theo thư mục
' hiện tại khi môi trường có NoDefaultCurrentDirectoryInExePath (đường dẫn có "\" thì không sao).
sh.Run "cmd /c cd /d """ & root & """ && call """ & root & "\stop-unimate.bat"" > server\stop-last.log 2>&1", 0, True

' Chạy server ẩn (0 = cửa sổ ẩn, False = không chờ). Output -> server\unimate.log
sh.Run "cmd /c cd /d """ & root & """ && .venv\Scripts\python.exe server\main.py > server\unimate.log 2>&1", 0, False

' 0.306.0: /open = cho server len roi MO dashboard (luc dang nhap may, luc cai xong). Chu repo 24/10/2026:
' "cai unimate tren win hoac mac thi cai khoi dong cung trinh duyet". Khong co /open (nut Cap nhat, start-unimate.bat)
' thi van chay ngam nhu cu, khong bat cua so nao. Mo dang cua so app giong UNI MATE.bat; chu trong file nay chi
' dung ASCII vi wscript doc file theo ANSI codepage.
If WScript.Arguments.Count > 0 Then
  If LCase(WScript.Arguments(0)) = "/open" Then MoDashboard
End If

Sub MoDashboard()
  Dim port, url, i, http, ok, cands, c
  port = sh.ExpandEnvironmentStrings("%UNIMATE_PORT%")
  If port = "%UNIMATE_PORT%" Or port = "" Then port = "7777"
  url = "http://127.0.0.1:" & port
  ok = False
  For i = 1 To 60
    WScript.Sleep 1000
    On Error Resume Next
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    http.setTimeouts 2000, 2000, 2000, 2000
    http.Open "GET", url & "/health", False
    http.Send
    If Err.Number = 0 Then
      If http.Status = 200 Then ok = True
    End If
    Err.Clear
    On Error GoTo 0
    If ok Then Exit For
  Next
  cands = Array(sh.ExpandEnvironmentStrings("%ProgramFiles(x86)%") & "\Microsoft\Edge\Application\msedge.exe", _
                sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Microsoft\Edge\Application\msedge.exe", _
                sh.ExpandEnvironmentStrings("%ProgramFiles%") & "\Google\Chrome\Application\chrome.exe", _
                sh.ExpandEnvironmentStrings("%LocalAppData%") & "\Google\Chrome\Application\chrome.exe")
  For Each c In cands
    If fso.FileExists(c) Then
      sh.Run """" & c & """ --app=" & url, 1, False
      Exit Sub
    End If
  Next
  sh.Run url, 1, False
End Sub
