Attribute VB_Name = "Bloomberg_Refresh"
Option Explicit

' =====================================================================
' Greybark Research - Bloomberg One-Click Refresh Macro
' =====================================================================
' This macro:
'   1. Creates a temporary _STAGING sheet
'   2. Writes BDH formulas for all series
'   3. Waits for Bloomberg to resolve
'   4. Copies values to data sheets
'   5. Deletes staging, updates CONFIG, saves
'
' Data sheet layout:
'   Row 3 = Bloomberg Tickers
'   Row 4 = BDH Fields
'   Row 5+ = Data (Col A = dates YYYY-MM)
' =====================================================================

Private Const ROWS_PER_SERIES As Long = 130
Private Const DATA_START_ROW As Long = 5
Private Const TICKER_ROW As Long = 3
Private Const FIELD_ROW As Long = 4
Private Const MAX_WAIT_SECONDS As Long = 300

Sub ACTUALIZAR()
    ' One-click Bloomberg data refresh
    Dim wb As Workbook: Set wb = ThisWorkbook
    Dim dataSheets As Variant
    dataSheets = Array("PMI", "China", "CDS", "Credit_Spreads", "EM_Spreads", "Real_Yields", "CPI_Componentes", "EPFR_Flows", "Positioning", "Valuaciones", "Volatility", "Macro_Conditions", "Chile", "Factor_Returns", "Intl_Curves")

    ' Check Bloomberg availability
    If Not IsBloombergAvailable() Then
        MsgBox "Bloomberg Excel Add-in no detectado." & vbCrLf & _
               "Abra Bloomberg Terminal y habilite el Add-in en Excel.", _
               vbExclamation, "Bloomberg Refresh"
        Exit Sub
    End If

    Dim answer As VbMsgBoxResult
    answer = MsgBox("Actualizar datos Bloomberg?" & vbCrLf & _
                    "Esto tomara ~2-3 minutos.", _
                    vbYesNo + vbQuestion, "Bloomberg Refresh")
    If answer <> vbYes Then Exit Sub

    Application.ScreenUpdating = False
    Application.Calculation = xlCalculationManual
    Application.StatusBar = "Bloomberg: Preparando..."

    ' Create staging sheet
    Dim wsStaging As Worksheet
    Set wsStaging = GetOrCreateSheet(wb, "_STAGING")
    wsStaging.Cells.Clear

    ' Calculate date range
    Dim startDate As String
    Dim endDate As String
    startDate = Format(DateAdd("m", -120, Date), "mm/dd/yyyy")
    endDate = Format(Date, "mm/dd/yyyy")

    ' Write BDH formulas to staging
    Dim seriesCount As Long: seriesCount = 0
    Dim i As Long

    For i = LBound(dataSheets) To UBound(dataSheets)
        Dim ws As Worksheet
        Set ws = Nothing
        On Error Resume Next
        Set ws = wb.Sheets(dataSheets(i))
        On Error GoTo 0
        If ws Is Nothing Then GoTo NextSheet

        Dim lastCol As Long
        lastCol = ws.Cells(TICKER_ROW, ws.Columns.Count).End(xlToLeft).Column

        Dim col As Long
        For col = 2 To lastCol
            Dim ticker As String
            Dim fld As String
            ticker = Trim(CStr(ws.Cells(TICKER_ROW, col).Value & ""))
            fld = Trim(CStr(ws.Cells(FIELD_ROW, col).Value & ""))

            If Len(ticker) > 0 And Len(fld) > 0 Then
                Dim baseRow As Long
                baseRow = seriesCount * ROWS_PER_SERIES + 1

                ' Metadata in columns D-F (for copy-back)
                wsStaging.Cells(baseRow, 4).Value = dataSheets(i)
                wsStaging.Cells(baseRow, 5).Value = col
                wsStaging.Cells(baseRow, 6).Value = ticker

                ' BDH formula
                wsStaging.Cells(baseRow, 1).Formula = _
                    "=BDH(""" & ticker & """,""" & fld & """,""" & _
                    startDate & """,""" & endDate & _
                    """,""periodicitySelection"",""MONTHLY"")"

                seriesCount = seriesCount + 1
            End If
        Next col
NextSheet:
    Next i

    If seriesCount = 0 Then
        MsgBox "No se encontraron series para actualizar.", vbInformation
        GoTo Cleanup
    End If

    Application.StatusBar = "Bloomberg: Calculando " & seriesCount & " series..."
    Application.Calculation = xlCalculationAutomatic
    Application.CalculateFull

    ' Wait for Bloomberg to resolve all formulas
    Application.StatusBar = "Bloomberg: Esperando respuesta..."
    If Not WaitForBloomberg(wsStaging, seriesCount) Then
        MsgBox "Timeout esperando Bloomberg (" & MAX_WAIT_SECONDS & "s)." & vbCrLf & _
               "Verifique la conexion a Bloomberg Terminal.", _
               vbExclamation, "Bloomberg Refresh"
        GoTo Cleanup
    End If

    ' Copy values from staging to data sheets
    Application.StatusBar = "Bloomberg: Copiando valores..."
    Dim copied As Long: copied = 0
    Dim s As Long

    For s = 0 To seriesCount - 1
        Dim bRow As Long: bRow = s * ROWS_PER_SERIES + 1
        Dim sheetName As String: sheetName = CStr(wsStaging.Cells(bRow, 4).Value)
        Dim colIdx As Long: colIdx = CLng(wsStaging.Cells(bRow, 5).Value)

        Dim wsTarget As Worksheet
        Set wsTarget = wb.Sheets(sheetName)

        ' Read BDH results: col A = dates, col B = values
        Dim r As Long
        For r = 0 To ROWS_PER_SERIES - 2
            Dim cellDate As Variant
            Dim cellVal As Variant
            cellDate = wsStaging.Cells(bRow + r, 1).Value
            cellVal = wsStaging.Cells(bRow + r, 2).Value

            If IsEmpty(cellDate) Then Exit For
            If Not IsDate(cellDate) Then Exit For

            ' Find matching row in target sheet (by year-month)
            Dim targetRow As Long
            targetRow = FindDateRow(wsTarget, CDate(cellDate))

            If targetRow > 0 And Not IsEmpty(cellVal) Then
                If IsNumeric(cellVal) Then
                    wsTarget.Cells(targetRow, colIdx).Value = CDbl(cellVal)
                    copied = copied + 1
                End If
            End If
        Next r
    Next s

Cleanup:
    ' Delete staging sheet
    Application.DisplayAlerts = False
    On Error Resume Next
    wb.Sheets("_STAGING").Delete
    On Error GoTo 0
    Application.DisplayAlerts = True

    ' Update CONFIG
    On Error Resume Next
    wb.Sheets("CONFIG").Cells(2, 2).Value = Format(Now, "yyyy-mm-dd hh:mm:ss")
    wb.Sheets("CONFIG").Cells(3, 2).Value = seriesCount
    On Error GoTo 0

    ' Save
    wb.Save

    Application.StatusBar = False
    Application.ScreenUpdating = True
    Application.Calculation = xlCalculationAutomatic

    MsgBox "Actualizacion completada" & vbCrLf & _
           "Series: " & seriesCount & vbCrLf & _
           "Valores copiados: " & copied & vbCrLf & _
           Format(Now, "dd/mm/yyyy hh:mm"), _
           vbInformation, "Bloomberg Refresh"
End Sub


Private Function FindDateRow(ws As Worksheet, targetDate As Date) As Long
    ' Find the row matching a given month (YYYY-MM format in col A)
    Dim r As Long
    For r = DATA_START_ROW To DATA_START_ROW + 130
        Dim cellVal As Variant
        cellVal = ws.Cells(r, 1).Value
        If IsEmpty(cellVal) Then Exit For

        ' Try as date object
        If IsDate(cellVal) Then
            If Year(CDate(cellVal)) = Year(targetDate) And _
               Month(CDate(cellVal)) = Month(targetDate) Then
                FindDateRow = r
                Exit Function
            End If
        End If

        ' Try as YYYY-MM string
        Dim s As String: s = CStr(cellVal)
        If Len(s) >= 7 And InStr(s, "-") > 0 Then
            Dim parts() As String
            parts = Split(s, "-")
            If UBound(parts) >= 1 Then
                On Error Resume Next
                Dim y As Long: y = CLng(parts(0))
                Dim m As Long: m = CLng(parts(1))
                On Error GoTo 0
                If y = Year(targetDate) And m = Month(targetDate) Then
                    FindDateRow = r
                    Exit Function
                End If
            End If
        End If
    Next r
    FindDateRow = 0
End Function


Private Function WaitForBloomberg(wsStaging As Worksheet, seriesCount As Long) As Boolean
    Dim elapsed As Long: elapsed = 0

    Do While elapsed < MAX_WAIT_SECONDS
        DoEvents
        Application.Wait Now + TimeSerial(0, 0, 2)
        elapsed = elapsed + 2

        ' Check if any cell still shows Bloomberg requesting status
        Dim stillWaiting As Boolean: stillWaiting = False
        Dim s As Long
        For s = 0 To seriesCount - 1
            Dim checkRow As Long: checkRow = s * ROWS_PER_SERIES + 1
            Dim cellText As String
            On Error Resume Next
            cellText = UCase(CStr(wsStaging.Cells(checkRow, 1).Text))
            On Error GoTo 0

            If InStr(cellText, "REQUESTING") > 0 Or _
               InStr(cellText, "#GETTING") > 0 Then
                stillWaiting = True
                Exit For
            End If
        Next s

        If Not stillWaiting Then
            WaitForBloomberg = True
            Exit Function
        End If

        Application.StatusBar = "Bloomberg: Esperando... " & elapsed & "s"
    Loop

    WaitForBloomberg = False
End Function


Private Function GetOrCreateSheet(wb As Workbook, sheetName As String) As Worksheet
    On Error Resume Next
    Set GetOrCreateSheet = wb.Sheets(sheetName)
    On Error GoTo 0

    If GetOrCreateSheet Is Nothing Then
        Set GetOrCreateSheet = wb.Sheets.Add(After:=wb.Sheets(wb.Sheets.Count))
        GetOrCreateSheet.Name = sheetName
    End If
    GetOrCreateSheet.Visible = xlSheetVisible
End Function


Private Function IsBloombergAvailable() As Boolean
    Dim addIn As COMAddIn
    On Error Resume Next
    For Each addIn In Application.COMAddIns
        If InStr(1, addIn.progID, "Bloomberg", vbTextCompare) > 0 Then
            If addIn.Connect Then
                IsBloombergAvailable = True
                Exit Function
            End If
        End If
    Next
    On Error GoTo 0
    IsBloombergAvailable = False
End Function
