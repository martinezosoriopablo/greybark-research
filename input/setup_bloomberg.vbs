
' =====================================================================
' Greybark Research - Bloomberg Setup (correr UNA sola vez)
' =====================================================================
' Este script:
'   1. Abre bloomberg_data.xlsx
'   2. Importa la macro VBA
'   3. Agrega un boton ACTUALIZAR en la hoja INSTRUCCIONES
'   4. Guarda como .xlsm (con macros)
'   5. Cierra todo
'
' Despues de esto, tu amigo solo abre el .xlsm y hace click en el boton.
' =====================================================================

Option Explicit

Dim fso, scriptDir, xlsxPath, basPath, xlsmPath
Dim xlApp, wb, wsInst, btn, shp

Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

xlsxPath = scriptDir & "\" & "bloomberg_data.xlsx"
basPath  = scriptDir & "\" & "bloomberg_macro.bas"
xlsmPath = scriptDir & "\" & "bloomberg_data.xlsm"

' Check files exist
If Not fso.FileExists(xlsxPath) Then
    MsgBox "No se encontro: " & xlsxPath, vbCritical, "Setup Bloomberg"
    WScript.Quit
End If
If Not fso.FileExists(basPath) Then
    MsgBox "No se encontro: " & basPath, vbCritical, "Setup Bloomberg"
    WScript.Quit
End If

' Delete old .xlsm if exists
If fso.FileExists(xlsmPath) Then
    fso.DeleteFile xlsmPath, True
End If

MsgBox "Setup Bloomberg" & vbCrLf & vbCrLf & _
       "Esto va a:" & vbCrLf & _
       "  1. Abrir el Excel" & vbCrLf & _
       "  2. Importar la macro" & vbCrLf & _
       "  3. Agregar boton ACTUALIZAR" & vbCrLf & _
       "  4. Guardar como .xlsm" & vbCrLf & vbCrLf & _
       "Toma ~10 segundos. Click OK para continuar.", _
       vbInformation, "Greybark Research - Setup"

' Open Excel
Set xlApp = CreateObject("Excel.Application")
xlApp.Visible = False
xlApp.DisplayAlerts = False

' Need to enable VBA access (Trust Center setting)
On Error Resume Next
xlApp.AutomationSecurity = 1  ' msoAutomationSecurityLow
On Error GoTo 0

Set wb = xlApp.Workbooks.Open(xlsxPath)

' Import VBA module
On Error Resume Next
wb.VBProject.VBComponents.Import basPath
If Err.Number <> 0 Then
    Err.Clear
    ' Try alternative: if Trust Access to VBA is disabled
    MsgBox "No se pudo importar la macro automaticamente." & vbCrLf & vbCrLf & _
           "Debes habilitar acceso a VBA:" & vbCrLf & _
           "  Excel > Archivo > Opciones > Centro de Confianza > " & vbCrLf & _
           "  Config del Centro de Confianza > Configuracion de Macros > " & vbCrLf & _
           "  Marcar 'Confiar en el acceso al modelo de objetos de proyectos de VBA'" & vbCrLf & vbCrLf & _
           "Luego vuelve a ejecutar este script.", _
           vbExclamation, "Setup Bloomberg"
    wb.Close False
    xlApp.Quit
    Set xlApp = Nothing
    WScript.Quit
End If
On Error GoTo 0

' Go to INSTRUCCIONES sheet
Set wsInst = wb.Sheets("INSTRUCCIONES")

' Add a big button (Form Control)
' Parameters: Left, Top, Width, Height
Set btn = wsInst.Buttons.Add(50, 30, 350, 80)
With btn
    .Caption = "ACTUALIZAR BLOOMBERG"
    .OnAction = "ACTUALIZAR"
    .Font.Size = 18
    .Font.Bold = True
    .Font.Name = "Segoe UI"
End With

' Also add a smaller note below the button
wsInst.Shapes.AddTextbox(1, 50, 120, 350, 30).TextFrame.Characters.Text = _
    "Click el boton para actualizar. Toma ~2-3 minutos."
wsInst.Shapes(wsInst.Shapes.Count).TextFrame.Characters.Font.Size = 10
wsInst.Shapes(wsInst.Shapes.Count).TextFrame.Characters.Font.Name = "Segoe UI"
wsInst.Shapes(wsInst.Shapes.Count).TextFrame.Characters.Font.Color = RGB(100, 100, 100)
wsInst.Shapes(wsInst.Shapes.Count).Fill.Visible = False
wsInst.Shapes(wsInst.Shapes.Count).Line.Visible = False

' Move the existing instructions text down
' (shift existing content in column A down by inserting rows at top)
wsInst.Rows("1:9").Insert

' Re-label row 1 with big title
wsInst.Cells(1, 1).Value = ""
wsInst.Cells(1, 1).Font.Size = 14

' Save as .xlsm (52 = xlOpenXMLWorkbookMacroEnabled)
wb.SaveAs xlsmPath, 52
wb.Close False

xlApp.Quit
Set xlApp = Nothing

MsgBox "Setup completado!" & vbCrLf & vbCrLf & _
       "Archivo creado: " & xlsmPath & vbCrLf & vbCrLf & _
       "Tu amigo solo necesita:" & vbCrLf & _
       "  1. Abrir " & fso.GetFileName(xlsmPath) & vbCrLf & _
       "  2. Habilitar macros si Excel lo pide" & vbCrLf & _
       "  3. Click en el boton ACTUALIZAR BLOOMBERG" & vbCrLf & vbCrLf & _
       "Listo! Este script no se necesita de nuevo.", _
       vbInformation, "Greybark Research - Setup"
