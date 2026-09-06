"""Generate the user manual PDF and a clearly named copy of the test handbook."""
from pathlib import Path
from xml.sax.saxutils import escape
import shutil
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

root=Path(__file__).resolve().parent
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TextFR',fontName='Helvetica',fontSize=10,leading=15,spaceAfter=10))
styles['Title'].textColor=colors.HexColor('#153b59')
styles['Heading1'].textColor=colors.HexColor('#153b59')
styles['Heading1'].fontSize=18
styles['Heading2'].textColor=colors.HexColor('#137c86')
styles['Heading2'].fontSize=12
story=[]
for block in (root/'InfoBridge_Manuel_utilisation.md').read_text(encoding='utf-8').strip().split('\n\n'):
 if block.startswith('# '):
  story.extend([Spacer(1,105),Paragraph(escape(block[2:]),styles['Title']),Spacer(1,30)])
 elif block.startswith('## '):
  story.extend([PageBreak(),Paragraph(escape(block[3:]),styles['Heading1']),Spacer(1,12)])
 elif block.startswith('### '):
  story.append(Paragraph(escape(block[4:]),styles['Heading2']))
 else:
  for line in block.splitlines(): story.append(Paragraph(escape(line),styles['TextFR']))

def footer(canvas,doc):
 canvas.saveState(); canvas.setStrokeColor(colors.HexColor('#cbd8df')); canvas.line(40,38,A4[0]-40,38)
 canvas.setFillColor(colors.HexColor('#526579')); canvas.setFont('Helvetica',8)
 canvas.drawString(40,24,'InfoBridge | Manuel d’utilisation | 05/09/2026')
 canvas.drawRightString(A4[0]-40,24,str(doc.page)); canvas.restoreState()
SimpleDocTemplate(str(root/'InfoBridge_Manuel_utilisation.pdf'),pagesize=A4,leftMargin=44,rightMargin=44,topMargin=42,bottomMargin=52,title='InfoBridge — Manuel d’utilisation',author='InfoBridge').build(story,onFirstPage=footer,onLaterPages=footer)
shutil.copyfile(root/'InfoBridge_Cahier_de_recette_tous_roles.pdf',root/'InfoBridge_Manuel_test.pdf')
print('User manual and test manual PDFs generated')
