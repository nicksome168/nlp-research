from abc import ABC, abstractmethod

import torch
from torch.nn import CrossEntropyLoss

from transformers import AutoModel, XLNetConfig
from transformers.modeling_utils import SequenceSummary
from transformers.modeling_outputs import MultipleChoiceModelOutput
from transformers.models.xlnet.modeling_xlnet import XLNetForMultipleChoiceOutput
# Creating the customized model, by adding a drop out and a dense layer on top of distil bert to get the final output for the model. 

class MultipleChoiceModel(torch.nn.Module):
    def __init__(self, model, d_model=768):
        super(MultipleChoiceModel, self).__init__()
        self.model = model
        self.base = AutoModel.from_pretrained(model)
        # bert or longformer
        self.dropout = torch.nn.Dropout(0.3)
        # xlnet
        self.sequence_summary = SequenceSummary(XLNetConfig)
        # common layers
        self.classifier = torch.nn.Linear(d_model, 1)

    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        position_ids=None,
        head_mask=None,
        inputs_embeds=None,
        labels=None,
        output_attentions=None,
        output_hidden_states=None,
    ):
        r"""
        labels (:obj:`torch.LongTensor` of shape :obj:`(batch_size,)`, `optional`):
            Labels for computing the multiple choice classification loss. Indices should be in ``[0, ...,
            num_choices-1]`` where :obj:`num_choices` is the size of the second dimension of the input tensors. (See
            :obj:`input_ids` above)
        """
        num_choices = input_ids.shape[1] if input_ids is not None else inputs_embeds.shape[1]

        input_ids = input_ids.view(-1, input_ids.size(-1)) if input_ids is not None else None
        attention_mask = attention_mask.view(-1, attention_mask.size(-1)) if attention_mask is not None else None
        token_type_ids = token_type_ids.view(-1, token_type_ids.size(-1)) if token_type_ids is not None else None
        position_ids = position_ids.view(-1, position_ids.size(-1)) if position_ids is not None else None
        inputs_embeds = (
            inputs_embeds.view(-1, inputs_embeds.size(-2), inputs_embeds.size(-1))
            if inputs_embeds is not None
            else None
        )

        outputs = self.base(
            input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            position_ids=position_ids,
            head_mask=head_mask,
            inputs_embeds=inputs_embeds,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
        )

        if 'xlnet' in self.model:
            output = outputs[0]

            output = self.sequence_summary(output)
            logits = self.classifier(output)

            reshaped_logits = logits.view(-1, num_choices)

            loss = None
            if labels is not None:
                loss_fct = CrossEntropyLoss()
                loss = loss_fct(reshaped_logits, labels.view(-1))

            return XLNetForMultipleChoiceOutput(
                loss=loss,
                logits=reshaped_logits,
                mems=outputs.mems,
                hidden_states=outputs.hidden_states,
                attentions=outputs.attentions,
            )

        elif 'bert' in self.model:
            pooled_output = outputs[1]

            pooled_output = self.dropout(pooled_output)
            logits = self.classifier(pooled_output)
            reshaped_logits = logits.view(-1, num_choices)

            loss = None
            if labels is not None:
                loss_fct = CrossEntropyLoss()
                loss = loss_fct(reshaped_logits, labels)

            output = (reshaped_logits,) + outputs[2:]

            return MultipleChoiceModelOutput(
                loss=loss,
                logits=reshaped_logits,
                hidden_states=outputs.hidden_states,
                attentions=outputs.attentions,
            )