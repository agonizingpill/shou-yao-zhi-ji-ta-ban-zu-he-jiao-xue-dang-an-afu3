        import {workspace} from '../workspace.js';
        import {el} from '../dom.js';

        const page = {
  "title": "不同纹样的判别轴",
  "module": "判别纠混签注",
  "caption": "判别纠混签注",
  "detail": "同台织架的已对拍样段沿监督判别轴布局。每组保留样段作验证。若该织架已有验收启用的外台校准，计算会自动借用来源织架模型并按该版换算；任务提交后版次即冻结，签注可查模型来源与校准版本。",
  "path": "/axes",
  "columns": [
    {
      "name": "code",
      "label": "编号"
    },
    {
      "name": "segment",
      "label": "待辨动作"
    },
    {
      "name": "suggestion",
      "label": "判别纹样"
    },
    {
      "name": "confidence",
      "label": "模型概率"
    },
    {
      "name": "holdout",
      "label": "留出正确率"
    },
    {
      "name": "model_loom",
      "label": "判别模型织架"
    },
    {
      "name": "calibration_version",
      "label": "借用校准版次"
    },
    {
      "name": "token",
      "label": "计算号"
    }
  ],
  "layout": "split",
  "view": "grid",
  "actions": [
    {
      "name": "fit_axes",
      "label": "计算踏板判别轴",
      "path": "/axes/fit-axes",
      "fields": [
        {
          "name": "segment",
          "label": "样段号",
          "kind": "text",
          "initial": "SEG-A"
        }
      ],
      "help": "默认使用同一台织架的三类已核对参考；该织架若有已启用校准，则自动借用来源织架模型与换算，提交时冻结版本。",
      "roles": [
        "operator",
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "fit_borrowed_axis",
      "label": "指定外台模型计算判别轴",
      "path": "/axes/fit-borrowed-axis",
      "fields": [
        {
          "name": "segment",
          "label": "样段号",
          "kind": "text",
          "initial": "SEG-NEW"
        },
        {
          "name": "source_loom",
          "label": "借出模型的织架号",
          "kind": "text",
          "initial": "LM-EAST"
        }
      ],
      "help": "按指定来源织架对应的已启用校准换算并判别；仍须复核员签注。",
      "roles": [
        "operator",
        "reviewer"
      ],
      "success": "已写入"
    },
    {
      "name": "record_axis",
      "label": "签注判别纠混",
      "path": "/axes/record-axis",
      "fields": [
        {
          "name": "code",
          "label": "签注号",
          "kind": "text",
          "initial": "AXIS-02"
        },
        {
          "name": "token",
          "label": "计算编号",
          "kind": "token",
          "initial": ""
        }
      ],
      "help": "置信和留出均合格才生成签注。",
      "roles": [
        "reviewer"
      ],
      "success": "已写入"
    }
  ]
};

        export const {title} = page;
        export const key = "axes";
        export async function render(root, role) {
          await workspace(root, role, page);

        }
