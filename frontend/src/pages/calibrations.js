import {workspace} from '../workspace.js';

const page = {
  title: '外台模型借用与校准',
  module: '模型借用校准',
  caption: '织架校准版本',
  detail: '样段少的新织架可按方向借用别台织架的判别模型：先用两架成对动作换算左右脚频与停顿，再用新织架另行留出的对拍样段验收，平纹、斜纹、缎纹各认对至少八成才启用。反向借用须独立验收。同一织架晚交并启用的版本不会被早交晚成的任务顶掉；模型与换算同版切换，验收失败保留旧版。判别签注可查模型来源织架与校准版次。',
  path: '/calibrations',
  columns: [
    {name: 'code', label: '校准版次'},
    {name: 'loom', label: '借用织架'},
    {name: 'source_loom', label: '模型来源织架'},
    {name: 'version', label: '提交版次'},
    {name: 'state', label: '状态'},
    {name: 'active', label: '当前启用'},
    {name: 'right_factor', label: '右脚换算'},
    {name: 'left_factor', label: '左脚换算'},
    {name: 'pause_factor', label: '停顿换算'},
    {name: 'accuracies', label: '分纹样正确率'},
    {name: 'token', label: '计算号'}
  ],
  layout: 'stack',
  view: 'table',
  actions: [
    {
      name: 'submit_calibration',
      label: '提交成对动作校准',
      path: '/calibrations/submit-calibration',
      fields: [
        {name: 'code', label: '校准版次号', kind: 'text', initial: 'CAL-01'},
        {name: 'loom', label: '新织架（借用方）', kind: 'text', initial: 'LM-WEST'},
        {name: 'source_loom', label: '模型来源织架（借出方）', kind: 'text', initial: 'LM-EAST'},
        {
          name: 'pairs',
          label: '成对样段编号（来源、新织架成对）',
          kind: 'json',
          initial: [
            ['SEG-S1', 'SEG-N1'],
            ['SEG-S2', 'SEG-N2'],
            ['SEG-S3', 'SEG-N3']
          ]
        }
      ],
      help: '每对是同一组踏板动作在两架织架上的样段编号；顺序写反也会按样段所属织架自动校正。提交后由 worker 计算换算系数与八成验收报告。',
      roles: ['operator', 'reviewer'],
      success: '已提交'
    },
    {
      name: 'accept_calibration',
      label: '验收八成并启用换版',
      path: '/calibrations/accept-calibration',
      fields: [
        {name: 'code', label: '校准版次号', kind: 'text', initial: 'CAL-01'},
        {name: 'token', label: '计算编号', kind: 'token', initial: ''}
      ],
      help: '三类纹样各认对至少八成才启用；不达标保留当前旧版。晚交版次启用后，更早提交的任务不能覆盖它。仅复核员可执行。',
      roles: ['reviewer'],
      success: '已启用'
    }
  ]
};

export const {title} = page;
export const key = 'calibrations';
export async function render(root, role) {
  await workspace(root, role, page);
}
