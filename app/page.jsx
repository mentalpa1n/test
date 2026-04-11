"use client";
import React, { useEffect, useState } from 'react';
import { supabase } from '../lib/supabase';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { Loader2, TrendingUp } from 'lucide-react';

// Регистрация модулей Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
);

export default function OrdersChart() {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      // Запрашиваем данные из таблицы
      const { data, error } = await supabase
        .from('orders')
        .select('created_at, total_sum')
        .order('created_at', { ascending: true });

      if (error) throw error;

      // Группируем данные по дням (Количество заказов)
      const aggregated = data.reduce((acc, order) => {
        if (!order.created_at) return acc;
        
        const date = new Date(order.created_at).toLocaleDateString('ru-RU');
        acc[date] = (acc[date] || 0) + 1; 
        return acc;
      }, {});

      setChartData({
        labels: Object.keys(aggregated),
        datasets: [
          {
            fill: true,
            label: 'Количество заказов',
            data: Object.values(aggregated),
            borderColor: 'rgb(59, 130, 246)',
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            tension: 0.4,
            pointRadius: 4,
            pointBackgroundColor: '#fff',
            borderWidth: 2,
          },
        ],
      });
    } catch (err) {
      console.error('Ошибка загрузки данных:', err.message);
    } finally {
      setLoading(false);
    }
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#1f2937',
        padding: 12,
        cornerRadius: 8,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        grid: { color: 'rgba(0, 0, 0, 0.05)' },
        ticks: { stepSize: 1 }
      },
      x: {
        grid: { display: false }
      }
    }
  };

  if (loading) {
    return (
      <div className="flex h-96 w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="text-xl font-semibold text-slate-800">Статистика заказов</h2>
            <p className="text-sm text-slate-500">Динамика продаж за последний период</p>
          </div>
          <div className="bg-blue-50 p-3 rounded-xl">
            <TrendingUp className="h-6 w-6 text-blue-600" />
          </div>
        </div>

        <div className="h-[400px] w-full">
          {chartData && <Line data={chartData} options={options} />}
        </div>
      </div>
    </div>
  );
}