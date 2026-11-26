from domain.looms_api import router as looms
from domain.segments_api import router as segments
from domain.axes_api import router as axes
from domain.lesson_demos_api import router as lesson_demos
from domain.calibrations_api import router as calibrations
from domain.workbench_api import router as workbench

routers = (calibrations, workbench, looms, segments, axes, lesson_demos,)
