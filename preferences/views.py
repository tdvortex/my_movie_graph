import json
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .models import Ranker, Item
from .cypher import (delete_direct_preference, delete_ranker, delete_ranker_knows, direct_preference_exists,
                     get_direct_preferences, insert_preference, insert_ranker_knows, ranker_knows_item)
from .serializers import RankerSerializer, ItemSerializer


@api_view(['GET'])
def items(request):
    if request.method == 'GET':
        # Get a list of all items
        serializer = ItemSerializer(Item.nodes.all(), many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        # Create a new item
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(data=serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(data={'validation_error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def ranker_list(request):
    if request.method == 'GET':
        # Get a list of all rankers
        serializer = RankerSerializer(Ranker.nodes.all(), many=True)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        # Create a new ranker
        serializer = RankerSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(data=serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(data={'validation_error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'DELETE'])
def ranker_detail(request, ranker_id: str):
    # Check if ranker exists
    ranker = Ranker.nodes.first_or_none(ranker_id=ranker_id)
    if not ranker:
        return Response(status=status.HTTP_404_NOT_FOUND, data={'error': f'Ranker with id {ranker_id} not found'})

    if request.method == 'GET':
        # Get a list of all preferences for this ranker
        data = json.dumps([[ItemSerializer(i).data, ItemSerializer(j).data]
                           for i, j in get_direct_preferences(ranker)])
        return Response(data=data, status=status.HTTP_200_OK)
    elif request.method == 'DELETE':
        delete_ranker(ranker)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST', 'DELETE'])
def ranker_knows(request, ranker_id: str, item_id: str):
    errors = {}

    # Check for existence of ranker and item
    ranker = Ranker.nodes.first_or_none(ranker_id=ranker_id)
    item = Item.nodes.first_or_none(item_id=item_id)
    if not ranker:
        errors['ranker_error'] = f'Ranker with id {ranker_id} not found'
    if not item:
        errors['item_error'] = f'Item with id {item_id} not found'

    # Throw 404 if anything is missing
    if errors:
        return Response(status=status.HTTP_404_NOT_FOUND, data=errors)

    if request.method == 'GET':
        # Check if the ranker knows the item
        if not ranker_knows_item:
            # If they don't, return 204
            return Response(status=status.HTTP_204_NO_CONTENT)

        # Otherwise return the serialized item
        serializer = ItemSerializer(item)
        return Response(data=serializer.data, status=status.HTTP_200_OK)
    elif request.method == 'POST':
        # Create the relationship if you need to
        result = insert_ranker_knows(ranker, item)
        serializer = ItemSerializer(item)

        if result == 'Exists':
            return Response(data=serializer.data, status=status.HTTP_200_OK)
        elif result == 'Created':
            return Response(data=serializer.data, status=status.HTTP_201_CREATED)
    elif request.method == 'DELETE':
        delete_ranker_knows(ranker, item)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'POST', 'DELETE'])
def ranker_pairwise_preference(request, ranker_id: str, preferred_id: str, nonpreferred_id: str):
    errors = {}

    # Check for existence of ranker, preferred, and nonpreferred
    ranker = Ranker.nodes.first_or_none(ranker_id=ranker_id)
    preferred = Item.nodes.first_or_none(item_id=preferred_id)
    nonpreferred = Item.nodes.first_or_none(item_id=nonpreferred_id)
    if not ranker:
        errors['ranker_error'] = f'Ranker with id {ranker_id} not found'
    if not preferred:
        errors['preferred_error'] = f'Item with id {preferred_id} not found'
    if not nonpreferred:
        errors['nonpreferred_error'] = f'Item with id {nonpreferred_id} not found'

    # Throw 404 if anything is missing
    if errors:
        return Response(status=status.HTTP_404_NOT_FOUND, data=errors)

    if request.method == 'GET':
        # Check if the requested preference exists
        if not direct_preference_exists(ranker, preferred, nonpreferred):
            # If it doesn't, return 204
            return Response(status=status.HTTP_204_NO_CONTENT)

        # If it does, return a JSON of the two serialized items in order of preference
        return Response(
            data=json.dumps([ItemSerializer(preferred).data,
                            ItemSerializer(nonpreferred).data]),
            status=status.HTTP_200_OK
        )
    elif request.method == 'POST':
        # Try to insert the preference, see if it works
        result = insert_preference(ranker, preferred, nonpreferred)

        # Return the appropriate response code
        if result == 'Invalid':
            return Response(
                status=status.HTTP_400_BAD_REQUEST,
                data={'cycle_error': f'Ranker {ranker_id} has a preference for {nonpreferred_id} over {preferred_id}, cycles not allowed'}
            )
        elif result == 'Exists':
            return Response(
                data=json.dumps([ItemSerializer(preferred).data,
                                ItemSerializer(nonpreferred).data]),
                status=status.HTTP_200_OK
            )
        elif result == 'Created':
            return Response(
                data=json.dumps([ItemSerializer(preferred).data,
                                ItemSerializer(nonpreferred).data]),
                status=status.HTTP_201_CREATED
            )
    elif request.method == 'DELETE':
        delete_direct_preference(ranker, preferred, nonpreferred)
        return Response(status=status.HTTP_204_NO_CONTENT)
