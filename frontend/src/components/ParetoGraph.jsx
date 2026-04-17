import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';

export default function ParetoGraph({ scenarios = [], selectedScenarioId = null }) {
  const chartData = scenarios.map((scenario) => ({
    id: scenario.scenario_id,
    node: scenario.target_node,
    cost: Number(scenario.estimated_cost_usd),
    risk: Number(scenario.predicted_failure_prob) * 100,
    latency: Number(scenario.predicted_latency_ms),
    energy: Number(scenario.estimated_energy_kwh),
    selected: scenario.scenario_id === selectedScenarioId,
  }));

  return (
    <div className="h-[420px] w-full rounded-[28px] border border-white/10 bg-slate-950/70 p-4 shadow-[0_24px_80px_rgba(2,6,23,0.42)]">
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <CartesianGrid strokeDasharray="4 4" stroke="#1e293b" />
          <XAxis
            type="number"
            dataKey="cost"
            name="Cost"
            unit=" USD"
            tick={{ fill: '#94a3b8' }}
            stroke="#334155"
          />
          <YAxis
            type="number"
            dataKey="risk"
            name="Failure risk"
            unit="%"
            tick={{ fill: '#94a3b8' }}
            stroke="#334155"
          />
          <ZAxis type="number" dataKey="latency" range={[80, 320]} name="Latency" unit=" ms" />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            contentStyle={{
              backgroundColor: 'rgba(2, 6, 23, 0.92)',
              border: '1px solid rgba(148, 163, 184, 0.18)',
              borderRadius: '1rem',
              boxShadow: '0 18px 50px rgba(2, 6, 23, 0.55)',
            }}
            formatter={(value, name) => {
              if (name === 'risk') {
                return [`${Number(value).toFixed(2)}%`, 'Failure risk'];
              }
              if (name === 'cost') {
                return [`$${Number(value).toFixed(4)}`, 'Estimated cost'];
              }
              if (name === 'latency') {
                return [`${Number(value).toFixed(2)} ms`, 'Latency'];
              }
              return [value, name];
            }}
            labelFormatter={(_, payload) => payload?.[0]?.payload?.node ?? 'Scenario'}
          />
          <Scatter data={chartData} fill="#378ADD">
            {chartData.map((entry) => (
              <Cell key={entry.id} fill={entry.selected ? '#38bdf8' : '#22c55e'} stroke={entry.selected ? '#bae6fd' : '#86efac'} strokeWidth={entry.selected ? 3 : 1} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
