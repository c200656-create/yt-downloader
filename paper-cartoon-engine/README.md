# paper-cartoon-engine

Движок для мультяшных роликов в стиле faceless-каналов про деньги (Python + pycairo → MP4 через ffmpeg).
Используется скиллом Claude `paper-cartoon-video`: скилл скачивает отсюда `engine.py` по метке версии.

- `engine.py` — персонажи (повороты, профиль, жесты), реквизит, 3D-предметы, свет и тени, дым/пар/огонь, камера, переходы, рендер.
- `examples/` — готовые ролики-образцы (`python3 v4_lamp_kitchen_fire.py out.mp4`, `... sheet 1 3 5` — контактный лист).

Запуск примеров: положить `engine.py` рядом с примером, установить `pycairo numpy` и шрифты Permanent Marker + Caveat Brush.
