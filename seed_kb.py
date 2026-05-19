import sqlite3

glossary = [
    # Procesador (CPU)
    (
        "Pasta térmica seca",
        "pasta termica, seca, cpu, procesador, sobrecalentamiento, calor, disipador",
        "El compuesto que transfiere el calor entre el procesador y el disipador se ha endurecido y agrietado. Actúa como aislante en lugar de conductor, provocando sobrecalentamiento inmediato.",
        "Procesador (CPU)"
    ),
    (
        "Pines doblados o rotos",
        "pines, doblados, rotos, cpu, socket, lga, pga, placa base",
        "Daño físico en los delicados contactos del procesador (PGA) o del socket de la placa base (LGA). Puede causar desde que la PC no encienda, hasta que no detecte la memoria RAM o la tarjeta de video.",
        "Procesador (CPU)"
    ),
    (
        "Procesador quemado (Cortocircuito)",
        "quemado, cortocircuito, cpu, procesador, voltaje, fuente de poder",
        "Daño interno irreversible, generalmente causado por un pico extremo de voltaje desde la placa base o la fuente de poder.",
        "Procesador (CPU)"
    ),
    (
        "Thermal Throttling (Estrangulamiento térmico)",
        "thermal throttling, estrangulamiento, termico, temperatura, cpu, rendimiento",
        "Un mecanismo de defensa. El procesador reduce drásticamente su velocidad de reloj (rendimiento) para bajar la temperatura y evitar derretirse.",
        "Procesador (CPU)"
    ),

    # Placa Base (Motherboard / Tarjeta Madre)
    (
        "Capacitores hinchados o reventados",
        "capacitores, condensadores, hinchados, reventados, placa base, motherboard, encendido",
        "Pequeños cilindros en la placa que filtran la energía. Cuando fallan, se abultan por arriba o derraman un líquido marrón, causando reinicios aleatorios o impidiendo el encendido.",
        "Placa Base (Motherboard / Tarjeta Madre)"
    ),
    (
        "Fallo en el VRM (Módulo Regulador de Voltaje)",
        "vrm, voltaje, placa base, motherboard, cpu, regulador",
        "Los componentes que convierten la energía de la fuente a un voltaje que el CPU puede usar se han quemado. La placa recibe energía, pero el CPU no.",
        "Placa Base (Motherboard / Tarjeta Madre)"
    ),
    (
        "BIOS Corrupta (Brickeada)",
        "bios, corrupta, uefi, brickeada, placa base, motherboard, actualizacion",
        "El software básico de la placa base se dañó, generalmente por un corte de luz durante una actualización. El equipo enciende los ventiladores, pero la pantalla se queda negra.",
        "Placa Base (Motherboard / Tarjeta Madre)"
    ),
    (
        "Pila CMOS agotada",
        "pila, cmos, bateria, cr2032, hora, fecha, bios, arranque",
        "La pequeña batería de botón (CR2032) se descargó. La PC pierde la hora, la fecha y la configuración de arranque cada vez que se desconecta de la corriente.",
        "Placa Base (Motherboard / Tarjeta Madre)"
    ),

    # Memoria RAM
    (
        "Módulo defectuoso (Chips fritos)",
        "ram, modulo, defectuoso, frito, bsod, pantallazo azul, windows, cuelgues",
        "Daño físico o electrónico en la memoria. Es la causa principal de los famosos \"Pantallazos Azules de la Muerte\" (BSOD) en Windows y de que las aplicaciones se cierren de golpe.",
        "Memoria RAM"
    ),
    (
        "Contactos oxidados o sucios",
        "contactos, oxidados, sucios, ram, polvo, humedad, video, pitidos",
        "Acumulación de polvo o humedad en los pines dorados de la RAM. Impide que la placa base la lea, lo que resulta en un equipo que enciende pero no da video (suele hacer pitidos de error).",
        "Memoria RAM"
    ),
    (
        "Incompatibilidad de frecuencias",
        "incompatibilidad, frecuencias, ram, velocidad, latencia, voltaje, sincronizar",
        "Usar memorias de diferentes velocidades, latencias o voltajes que el controlador de memoria no logra sincronizar, causando inestabilidad del sistema.",
        "Memoria RAM"
    ),

    # Almacenamiento (HDD y SSD)
    (
        "Sectores defectuosos",
        "sectores, defectuosos, hdd, ssd, disco, lento, corrompen, arranque",
        "Áreas del disco magnético o de los chips de memoria que ya no pueden retener datos. Causa que el sistema operativo se congele, se corrompan archivos o tarde muchísimo en arrancar.",
        "Almacenamiento (HDD y SSD)"
    ),
    (
        "Daño mecánico (\"Click of Death\")",
        "danio mecanico, click of death, hdd, disco duro, ruidos, clic",
        "Exclusivo de los discos duros tradicionales (HDD). El brazo mecánico que lee los datos choca internamente haciendo un sonido rítmico de \"clic\". Significa la muerte inminente del disco.",
        "Almacenamiento (HDD y SSD)"
    ),
    (
        "Desgaste de celdas NAND",
        "desgaste, celdas, nand, ssd, estado solido, tbw, lectura, datos",
        "Exclusivo de los discos de estado sólido (SSD). Las celdas han alcanzado su límite de reescrituras (TBW) y la unidad se bloquea en modo de \"solo lectura\" para evitar la pérdida de los datos existentes.",
        "Almacenamiento (HDD y SSD)"
    ),

    # Tarjeta Gráfica (GPU)
    (
        "Artifacts (Artefactos visuales)",
        "artifacts, artefactos, visuales, gpu, grafica, vram, calor, pantalla",
        "Aparición de cuadros de colores, líneas extrañas o destellos geométricos en la pantalla. Suele indicar que la memoria de video (VRAM) o el propio chip gráfico se están muriendo por calor excesivo.",
        "Tarjeta Gráfica (GPU)"
    ),
    (
        "Fallo de soldadura (Requiere Reballing)",
        "soldadura, falla, reballing, gpu, grafica, estaño, calor",
        "Las microscópicas esferas de estaño que unen el chip gráfico a su placa se han agrietado por la dilatación térmica de calentarse y enfriarse miles de veces.",
        "Tarjeta Gráfica (GPU)"
    ),
    (
        "Ventiladores bloqueados/muertos",
        "ventiladores, bloqueados, muertos, gpu, grafica, polvo, calor, apagado",
        "El sistema de enfriamiento falla por acumulación de polvo o falla del motor. La tarjeta se sobrecalienta en minutos al abrir un juego y apaga la PC por seguridad.",
        "Tarjeta Gráfica (GPU)"
    ),

    # Fuente de Alimentación (PSU)
    (
        "Voltaje inestable (Rizado alto)",
        "voltaje, inestable, rizado, psu, fuente, energia, apagones",
        "La fuente no entrega un flujo limpio de energía (los 12V, 5V y 3.3V fluctúan demasiado). Esto degrada lentamente todos los componentes de la PC y causa apagones bajo carga pesada.",
        "Fuente de Alimentación (PSU)"
    ),
    (
        "Fusible o Varistor quemado",
        "fusible, varistor, quemado, psu, fuente, descarga, proteccion",
        "Componentes internos de protección que se sacrificaron para detener un pico de tensión severo (como un rayo) y evitar que llegue al resto de la computadora.",
        "Fuente de Alimentación (PSU)"
    ),
    (
        "Fallo del riel de 12V",
        "riel, 12v, psu, fuente, ventiladores, cpu, gpu, energia",
        "La fuente enciende y hace girar los ventiladores (que usan 5V), pero no puede entregar la potencia fuerte (12V) que necesitan el procesador y la tarjeta gráfica para operar.",
        "Fuente de Alimentación (PSU)"
    )
]

def seed():
    conn = sqlite3.connect('taller_prototipo.db')
    c = conn.cursor()
    c.execute("DELETE FROM knowledge_base")
    c.executemany("INSERT INTO knowledge_base (title, keywords, content, category) VALUES (?, ?, ?, ?)", glossary)
    conn.commit()
    conn.close()
    print("Seed exitoso de la Base de Conocimientos.")

if __name__ == "__main__":
    seed()
