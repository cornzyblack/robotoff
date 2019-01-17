import itertools

import dataclasses

import falcon
from falcon_cors import CORS

from robotoff.app.core import (normalize_lang,
                               get_random_category_prediction,
                               parse_product_json,
                               get_category_name,
                               save_category_annotation,
                               get_category_prediction,
                               get_insights,
                               get_random_insight,
                               save_insight)
from robotoff.ingredients import generate_corrections, generate_corrected_text
from robotoff.utils.es import get_es_client

es_client = get_es_client()


class CategoryPredictionResource:
    def on_get(self, req, resp):
        response = {}

        campaign = req.get_param('campaign')
        country = req.get_param('country')
        category = req.get_param('category')
        lang = normalize_lang(req.get_param('lang'))

        result = get_random_category_prediction(campaign, country, category)

        if result is None:
            response['status'] = "no_prediction_left"

        else:
            task, product = result
            response['product'] = parse_product_json(product, lang)
            response['task_id'] = str(task.id)

            predicted_category_name = get_category_name(task.predicted_category,
                                                        lang)
            response['prediction'] = {
                'confidence': task.confidence,
                'id': task.predicted_category,
                'name': predicted_category_name,
            }

        resp.media = response


class ProductInsightResource:
    def on_get(self, req, resp, barcode):
        response = {}
        insights = get_insights(barcode)

        if not insights:
            response['status'] = "no_insights"
        else:
            response['insights'] = insights
            response['status'] = "found"

        resp.media = response


class RandomInsightResource:
    def on_get(self, req, resp):
        insight_type = req.get_param('type') or None
        country = req.get_param('country') or None
        response = {}

        insight = get_random_insight(insight_type, country)

        if not insight:
            response['status'] = "no_insights"
        else:
            response['insight'] = insight.serialize()
            response['status'] = "found"

        resp.media = response


class AnnotateInsightResource:
    def on_post(self, req, resp):
        insight_id = req.get_param('insight_id', required=True)
        annotation = req.get_param_as_int('annotation', required=True,
                                          min=-1, max=1)

        save = req.get_param_as_bool('save')

        if save is None:
            save = True

        save_insight(insight_id, annotation, save=save)
        resp.media = {
            'status': 'saved',
        }


class CategoryPredictionByProductResource:
    def on_get(self, req, resp, barcode):
        response = {}

        lang = normalize_lang(req.get_param('lang'))

        result = get_category_prediction(barcode)

        if result is None:
            response['status'] = "no_prediction_left"

        else:
            task, product = result
            response['product'] = parse_product_json(product, lang)
            response['task_id'] = str(task.id)

            predicted_category_name = get_category_name(task.predicted_category,
                                                        lang)
            response['prediction'] = {
                'confidence': task.confidence,
                'id': task.predicted_category,
                'name': predicted_category_name,
            }

        resp.media = response


class CategoryAnnotateResource:
    def on_post(self, req, resp):
        task_id = req.get_param('task_id', required=True)
        annotation = req.get_param_as_int('annotation', required=True,
                                          min=-1, max=1)

        save = req.get_param_as_bool('save')

        if save is None:
            save = True

        save_category_annotation(task_id, annotation, save=save)
        resp.media = {
            'status': 'saved',
        }


class IngredientSpellcheckResource:
    def on_post(self, req, resp):
        text = req.get_param('text', required=True)

        corrections = generate_corrections(es_client, text, confidence=1)
        term_corrections = list(itertools.chain
                                .from_iterable((c.term_corrections
                                                for c in corrections)))

        resp.media = {
            'corrections': [dataclasses.asdict(c) for c in corrections],
            'text': text,
            'corrected': generate_corrected_text(term_corrections, text),
        }


cors = CORS(allow_all_origins=True,
            allow_all_headers=True,
            allow_all_methods=True)

api = falcon.API(middleware=[cors.middleware])
# Parse form parameters
api.req_options.auto_parse_form_urlencoded = True
api.add_route('/api/v1/insights/{barcode}', ProductInsightResource())
api.add_route('/api/v1/insights/random', RandomInsightResource())
api.add_route('/api/v1/insights/annotate', AnnotateInsightResource())
api.add_route('/api/v1/categories/predictions', CategoryPredictionResource())
api.add_route('/api/v1/categories/predictions/{barcode}',
              CategoryPredictionByProductResource())
api.add_route('/api/v1/categories/annotate', CategoryAnnotateResource())
api.add_route('/api/v1/predict/ingredients/spellcheck', IngredientSpellcheckResource())
