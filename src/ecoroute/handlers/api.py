from mangum import Mangum

from ecoroute.main import app

handler = Mangum(app, lifespan="off")
