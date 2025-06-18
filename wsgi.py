#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from vidya.app import create_app
from vidya.config import ProductionConfig

app = create_app(config_class=ProductionConfig)


if __name__ == '__main__':
    app.run(host=ProductionConfig.DB_SERVER, port=ProductionConfig.PORT)
