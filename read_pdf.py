import sys
try:
    import PyPDF2
    reader = PyPDF2.PdfReader(r'c:\Users\Raul Alberto\Documents\Arqui\saas-hardware-repair-python\Documentación\Formato de Proyecto de Intervencion (1) (2).pdf')
    print("Número de páginas:", len(reader.pages))
    print("Primeras 500 letras de la página 1:")
    print(reader.pages[0].extract_text()[:500])
except Exception as e:
    print("Error:", e)
