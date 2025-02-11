#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import yfinance as yf
import pandas as pd
from datetime import timedelta

class IntradayDataDownloader:
    """
    Clase para descargar datos intradiarios usando yfinance, iterando en bloques
    debido a las limitaciones en la cantidad de datos disponibles en cada consulta.

    Se puede configurar el número total de días históricos a descargar (parámetro historical_days).
    Para intervalos en minutos (ej. "1m", "2m", "5m", "15m", "30m") se limita el histórico a 30 días,
    mientras que para intervalos mayores (ej. "60m", "90m", "1h") se pueden usar periodos mayores.
    """

    def __init__(self, ticker, interval, chunk_days=None, historical_days=None, output_dir="intraday/short-term"):
        """
        :param ticker: Símbolo del activo, por ejemplo "BTC-USD"
        :param interval: Intervalo de los datos, ej. "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"
        :param chunk_days: Número de días en cada bloque para la descarga.
                           Si no se especifica, se usa 8 días para '1m' y 15 para los demás intervalos.
        :param historical_days: Número total de días históricos a descargar.
                                Si no se especifica, se usa:
                                  - 30 días para intervalos en minutos (menores a 60m),
                                  - 90 días para intervalos de 60m en adelante.
        :param output_dir: Directorio donde se guardará el archivo CSV resultante.
        """
        self.ticker = ticker
        self.interval = interval
        self.output_dir = output_dir
        # Crear el directorio de salida si no existe.
        os.makedirs(self.output_dir, exist_ok=True)

        now = pd.Timestamp.now()

        # Determinar el total de días históricos según el intervalo.
        if historical_days is None:
            if self.interval in ['1m', '2m', '5m', '15m', '30m']:
                historical_days = 30
            elif self.interval in ['60m', '90m', '1h']:
                historical_days = 90
            else:
                historical_days = 30  # Valor por defecto
        else:
            # Si se proporciona un valor para historical_days pero el intervalo es en minutos,
            # se ajusta a 30 días (límite impuesto por Yahoo Finance).
            if self.interval in ['1m', '2m', '5m', '15m', '30m'] and historical_days > 30:
                print("Para datos de intervalos menores a 60m solo se permite un histórico máximo de 30 días. "
                      "Se ajusta historical_days a 30.")
                historical_days = 30

        self.end_date = now
        # Se suma un día al inicio para ajustar correctamente el rango.
        self.start_date = now - timedelta(days=historical_days) + timedelta(days=1)

        # Establecer chunk_days por defecto según el intervalo.
        if chunk_days is None:
            if self.interval == '1m':
                chunk_days = 8  # Máximo permitido para 1 minuto.
            else:
                chunk_days = 15
        else:
            if self.interval == '1m' and chunk_days > 8:
                print("Para datos '1m', se permite un máximo de 8 días por consulta. Se ajusta chunk_days a 8.")
                chunk_days = 8

        self.max_chunk = timedelta(days=chunk_days)
        self.adjust_dates()

    def adjust_dates(self):
        """
        Ajusta la fecha de fin si está en el futuro.
        """
        now = pd.Timestamp.now()
        if self.end_date > now:
            print(f"La fecha de fin solicitada ({self.end_date.date()}) es posterior a hoy. "
                  f"Se ajusta a hoy ({now.date()}).")
            self.end_date = now

    def flatten_columns(self, df):
        """
        Aplana las columnas del DataFrame. Si alguna columna es una tupla (por ejemplo,
        ('Open', 'BTC-USD')), se queda con el primer elemento.
        También renombra la columna 'Datetime' a 'Date'.
        """
        new_columns = []
        for col in df.columns:
            if isinstance(col, tuple):
                new_columns.append(col[0])
            else:
                new_columns.append(col)
        df.columns = new_columns

        if "Datetime" in df.columns:
            df.rename(columns={"Datetime": "Date"}, inplace=True)

        return df

    def download(self, save_csv=True):
        """
        Descarga datos intradiarios iterando en bloques y los concatena en un único DataFrame.

        :param save_csv: Si True, guarda el DataFrame concatenado en un archivo CSV.
        :return: DataFrame con todos los datos descargados.
        """
        data_frames = []
        current_start = self.start_date

        while current_start < self.end_date:
            current_end = min(current_start + self.max_chunk, self.end_date)
            print(f"Descargando datos de {current_start.date()} a {current_end.date()} para intervalo {self.interval}")

            try:
                df = yf.download(
                    self.ticker,
                    start=current_start.strftime("%Y-%m-%d"),
                    end=current_end.strftime("%Y-%m-%d"),
                    interval=self.interval,
                    progress=False
                )
                if not df.empty:
                    df.reset_index(inplace=True)
                    df = self.flatten_columns(df)
                    data_frames.append(df)
                else:
                    print("  No se obtuvieron datos en este periodo.")
            except Exception as e:
                print(f"  Error descargando datos de {current_start.date()} a {current_end.date()}: {e}")

            current_start = current_end

        if data_frames:
            result = pd.concat(data_frames, ignore_index=True)
            # Se eliminan duplicados basándose en la primera columna (normalmente la fecha)
            result.drop_duplicates(subset=result.columns[0], keep='first', inplace=True)
            if save_csv:
                filename = os.path.join(self.output_dir, f"{self.ticker}_{self.interval}.csv")
                result.to_csv(filename, index=False, lineterminator='\n')
                print(f"Datos guardados en: {filename}")
            return result
        else:
            print("No se han descargado datos.")
            return pd.DataFrame()


if __name__ == "__main__":
    # 1. Cargar el fichero cryptos.txt (ahora contiene solo tickers)
    with open("cryptos.txt", "r", encoding="utf-8") as f:
        tickers = json.load(f)

    # 2. Definir intervalos intradiarios y días históricos por intervalo
    intervalos = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h']
    historicos = {
        '1m': 30,
        '2m': 30,
        '5m': 30,
        '15m': 30,
        '30m': 30,
        '60m': 90,
        '90m': 60,
        '1h': 90
    }

    # 3. Procesar cada ticker definido en cryptos.txt
    for ticker in tickers:
        print("\n===========================================")
        print(f"Procesando datos para {ticker}")
        # Se construye la ruta de salida usando el ticker.
        # Por ejemplo, para "BTC-USD" se utilizará el nombre de carpeta "btc".
        folder_name = ticker.split("-")[0].lower()
        output_directory = os.path.join(folder_name, "intraday", "short-term")
        for interval in intervalos:
            print("\n------------------------------")
            print(f"Iniciando descarga para intervalo: {interval}")
            hd = IntradayDataDownloader(
                ticker=ticker,
                interval=interval,
                historical_days=historicos.get(interval),
                output_dir=output_directory
            )
            df_intraday = hd.download(save_csv=True)
